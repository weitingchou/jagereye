import ray
import time
import asyncio
import os
import cv2
from collections import deque

import tasks

from jagereye.api import APIConnector
from jagereye.neural_network.nn_manager import NeuralNetworkManager
from jagereye.neural_network.models import ObjectDetection
from jagereye.streaming import VideoStreamReader, VideoStreamWriter
from jagereye.util import logging
import jagereye.streaming.streaming as streaming


def load_category_index(path):
    with open(path, "r") as f:
        lines = f.readlines()
    result = dict()
    for line in lines:
        record = line.strip().split(" ")
        result[int(record[0])] = record[1]
    return result


def get_params(params, key):
    return params[key] if key in params else None


class IndexedDict(object):
    def __init__(self):
        self._keys = []
        self._values = []

    def insert(self, key, value):
        if key not in self._keys:
            self._keys.append(key)
            self._values.append(value)
        else:
            self._values[self._keys.index(key)] = value

    def remove(self, key):
        try:
            idx = self._keys.index(key)
            del self._keys[idx]
            del self._values[idx]
        except ValueError:
            raise KeyError(key)

    def key(self, key):
        try:
            idx = self._keys.index(key)
            return self._values[idx]
        except ValueError:
            raise KeyError(key)

    def keys(self):
        return self._keys

    def values(self):
        return self._values

    def kindex(self, idx):
        try:
            return self._keys[idx]
        except IndexError:
            raise IndexError("Index out of range")

    def vindex(self, idx):
        try:
            return self._values[idx]
        except IndexError:
            raise IndexError("Index out of range")


class VideoReaderClient(object):
    """
    Proxy class for VideoStreamReader.
    """
    def __init__(self, url):
        self._url = url
        self._reader = VideoStreamReader.remote()
        self._metadata = None
        self._opened = False

    @property
    def url(self):
        return self._url

    @property
    def metadata(self):
        if self._metadata is None:
            raise RuntimeError("Source stream has not enabled yet!")
        return self._metadata

    @property
    def opened(self):
        return self._opened

    def _start(self):
        if self._opened:
            return
        if ray.get(self._reader.open.remote(self._url)) != streaming.RETCODE["SUCCESS"]:
            logging.error("Failed to open source: {}".format(self._url))
            raise RuntimeError()
        self._metadata = ray.get(self._reader.get_metadata.remote())
        self._opened = True
        logging.info("Source started, url: {}".format(self._url))
        logging.info("metadata: {}".format(self._metadata))

    def restart(self, url=None):
        logging.info("Restarting source, url: {}".format(url))
        if url:
            self._url = url
        self.stop()
        self._start()

    def start(self):
        logging.info("Starting source, url: {}".format(self._url))
        self._start()

    def stop(self):
        logging.info("Stopping source, url: {}".format(self._url))
        ray.get(self._reader.release.remote())
        self._opened = False

    def read(self, batch_size):
        if not self._opened:
            raise RuntimeError()
        ret, frames = ray.get(self._reader.read.remote(batch_size))
        if ret == streaming.RETCODE["CONNECTION_BROKEN"]:
            raise RuntimeError()
        return frames


class EndOfMarginError(Exception):
    pass


class VideoMarginWriterClient(object):
    def __init__(self, out_dir, video_format, fps, margin):
        self._writer = VideoStreamWriter.remote()
        self._out_dir = out_dir
        self._video_format = video_format
        self._fps = fps
        self._opened = False

        self._max_margin_in_frames = self._fps * margin
        self._back_margin_q = deque(maxlen=self._max_margin_in_frames)
        self._front_margin_counter = 0

    def open(self, filename, size):
        if self._opened:
            raise RuntimeError()
        if not isinstance(filename, str):
            filename = "{}".format(filename)
        filepath = os.path.join(self._out_dir, filename)
        ret = ray.get(self._writer.open.remote(filepath,
                                               self._video_format,
                                               self._fps,
                                               size))
        if ret != streaming.RETCODE["SUCCESS"]:
            raise RuntimeError()
        for _ in range(len(self._back_margin_q)):
            self._writer.write.remote(self._back_margin_q.popleft())
        self._opened = True

    def append_back_margin_queue(self, frames):
        for f in frames:
            self._back_margin_q.append(f)

    def clear_back_margin_queue(self):
        self._back_margin_q.clear()

    def reset_front_margin(self):
        self._front_margin_counter = 0

    def write(self, frames):
        self._writer.write.remote(frames)
        self._front_margin_counter += len(frames)
        if self._front_margin_counter >= self._max_margin_in_frames:
            ray.get(self._writer.end.remote())
            self.reset_front_margin()
            self._opened = False
            raise EndOfMarginError()


STATE = {"NORMAL": 0, "ALERTING": 1}
RETCODE = {"SUCCESS": 0, "SOURCE_NOT_OPEN": 1, "SOURCE_DOWN": 2}


@ray.remote
class IntrusionDetectionActor(object):
    def __init__(self,
                 source,
                 roi,
                 triggers,
                 nn_manager,
                 motion_threshold,
                 detect_threshold,
                 fps,
                 event_video_format,
                 event_video_margin):
        # TODO: detect_in_region() should be modified to process this roi format
        self._roi = (roi[0]["x"], roi[0]["y"], roi[1]["x"], roi[1]["y"])
        self._triggers = triggers
        self._motion_threshold = motion_threshold or 80
        self._detect_threshold = detect_threshold or 0.25
        self._category_index = load_category_index("./coco.labels")
        self._nn_manager = nn_manager
        self._state = STATE["NORMAL"]

        self._source = VideoReaderClient(source["url"])
        sink_options = {
            "out_dir": "./",
            "video_format": event_video_format or "avi",
            "fps": fps or 15,
            "margin": event_video_margin or 3
        }
        self._video_out = VideoMarginWriterClient(**sink_options)
        logging.info("IntrusionDetectionActor has been created (source url: {}, "
                     "roi: {}, triggers: {}, motion_threshold: {}, "
                     "detect_threshold: {}".format(self._source.url,
                                                   self._roi,
                                                   self._triggers,
                                                   self._motion_threshold,
                                                   self._detect_threshold))

    def configure(self, params):
        logging.info("Configuring IntrusionDetectionActor, params: {}".format(params))
        if "source" in params and params["source"]["url"] != self._source.url:
            self._source.restart(params["source"]["url"])
        if "roi" in params:
            self._roi = params["roi"]
        if "triggers" in params:
            self._triggers = params["triggers"]
        if "motion_threshold" in params:
            self._motion_threshold = params["motion_threshold"]
        if "detect_threshold" in params:
            self._detect_threshold = params["detect_threshold"]
        return RETCODE["SUCCESS"]

    def _run_pipeline(self, frames):
        motion = tasks.detect_motion(frames, self._motion_threshold)
        detect = ray.get(self._nn_manager.run_model.remote("ObjectDetection",
                                                           [frames[idx]
                                                            for idx in motion]))
        catched = tasks.detect_in_region(self._source.metadata["height"],
                                         self._source.metadata["width"],
                                         detect,
                                         self._category_index,
                                         self._roi,
                                         self._triggers,
                                         self._detect_threshold)
        return catched

    def _process_event(self, catched, frames):
        self._video_out.append_back_margin_queue(frames)
        timestamp = frames[0]["timestamp"]
        if self._state == STATE["NORMAL"]:
            if any(catched):
                size = (self._source.metadata["width"],
                        self._source.metadata["height"])
                try:
                    self._video_out.open(timestamp, size)
                    logging.info("Creating event video: {}".format(timestamp))
                except RuntimeError as e:
                    logging.error(e)
                    raise
                self._state = STATE["ALERTING"]
        elif self._state == STATE["ALERTING"]:
            if any(catched):
                self._video_out.reset_front_margin()
            try:
                self._video_out.write(frames)
            except EndOfMarginError:
                logging.info("End of event video")
                self._state = STATE["NORMAL"]

    def run(self, batch_size=1, iterations=10):
        if not self._source.opened:
            self._source.start()

        result = RETCODE["SUCCESS"]
        for _ in range(iterations):
            try:
                frames = self._source.read(batch_size)
            except RuntimeError as e:
                logging.error(e)
                result = RETCODE["SOURCE_DOWN"]
                break
            """
            motion, detect, catched = self._run_pipeline(frames)
            self._process_event(catched, frames)
            print(catched)

            drawn_images = []
            if any(catched):
                drawn_images = [tasks.draw_tripwire(frame,
                                                    self._roi,
                                                    (66, 194, 244))
                                for frame in frames]
            else:
                drawn_images = [tasks.draw_tripwire(frame,
                                                    self._roi,
                                                    (226, 137, 59))
                                for frame in frames]
            for image in drawn_images:
                cv2.imshow("frame", image)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                time.sleep(0.066)
            """
        return result


class Analyzer(object):
    def __init__(self, name, source, pipelines, nn_manager):
        self._name = name
        self._nn_manager = nn_manager

        self._pipelines = []
        for p in pipelines:
            if p["type"] == "IntrusionDetection":
                self._pipelines.append(IntrusionDetectionActor.remote(source,
                                                                      p["params"]["roi"],
                                                                      p["params"]["triggers"],
                                                                      self._nn_manager,
                                                                      None,
                                                                      None,
                                                                      None,
                                                                      None,
                                                                      None))

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    def configure(self, source):
        # TODO: need implementation
        pass

    def run(self):
        return [p.run.remote(batch_size=5) for p in self._pipelines]


class AnalyzerDriver(APIConnector):


    def __init__(self,
                 io_loop,
                 nats_hosts=None,
                 nn_manager=None):
        super().__init__("analyzer", io_loop, nats_hosts)
        if nn_manager is None:
            raise RuntimeError("NeuralNetworkManager was not defined")
        else:
            self._nn_manager = nn_manager
        self._event_dir = "./"
        self._category_index_path = "./coco.labels"
        self._actives = IndexedDict()
        self._inactives = IndexedDict()
        self._actor = None

    def on_create(self, params):
        logging.info("Creating Analyzer, params: {}".format(params))
        try:
            sid = params["id"]
            name = params["name"]
            source = params["source"]
            pipelines = params["pipelines"]
            self._actives.insert(sid, Analyzer(name,
                                               source,
                                               pipelines,
                                               self._nn_manager))
        except KeyError:
            raise RuntimeError("Invalid request format")

    def on_read(self, params):
        try:
            # TODO: Need to find a way to return status of `SOURCE DOWN`
            get_status = lambda s: "RUNNING" if s in self._actives.keys() else "PAUSED"
            sid = params["id"]
            result = None
            if isinstance(sid, list):
                for s in sid:
                    result = {s: get_status(s)}
            else:
                result = get_status(sid)
            return result
        except Exception:
            # TODO: Need to handle error more specificly
            raise

    def on_update(self, params):
        logging.info("Updating Analyzer, params: {}".format(params))
        try:
            sid = params["id"]
            target = None
            if sid in self._actives.keys():
                target = self._actives.key(sid)
            else:
                target = self._inactives.key(sid)
        except KeyError:
            logging.error("Invalid request: {}".format(params))
            raise
        else:
            ret = ray.get(target.configure.remote(params))
            if ret == RETCODE["SOURCE_NOT_OPEN"]:
                raise RuntimeError()

    def on_delete(self, params):
        try:
            # TODO: Need to make sure the allocated resources for analyzer "sid"
            #       also been deleted completely
            remove = lambda x: self._actives.remove(x) if x in self._actives.keys() else self._inactives.remove(x)
            if isinstance(params, list):
                for sid in params:
                    remove(sid)
            else:
                remove(sid)
        except KeyError:
            raise RuntimeError("Invalid request foramt")

    def _activate(self, sid):
        try:
            if sid not in self._actives.keys():
                self._actives.insert(sid, self._inactives.key(sid))
                self._inactives.remove(sid)
        except Exception:
            raise

    def _deactivate(self, sid):
        try:
            if sid not in self._inactives.keys():
                self._inactives.insert(sid, self._actives.key(sid))
                self._actives.remove(sid)
        except Exception:
            raise

    def on_start(self, params):
        logging.info("Starting IntrusionDetectionActor, params: {}".format(params))
        if isinstance(params, list):
            for sid in params:
                self._activate(sid)
        else:
            self._activate(params)

    def on_stop(self, params):
        logging.info("Stoping IntrusionDetectionActor, params: {}".format(params))
        if isinstance(params, list):
            for sid in params:
                self._deactivate(sid)
        else:
            self._deactivate(params)

    async def start(self, delay=0):
        logging.info("Driver '{}' started".format(self.__class__.__name__))
        while True:
            tasks = []
            for analyzer in self._actives.values():
                tasks.extend(analyzer.run())
            if not tasks:
                await asyncio.sleep(1)
                continue
            await asyncio.sleep(delay)
            for idx, ret in enumerate(ray.get(tasks)):
                if ret == RETCODE["SOURCE_DOWN"]:
                    logging.error("Connection broke for the source of analyzer"
                                  " '{}'.".format(self._actives.kindex(idx)))
                    self._deactivate(self._actives.kindex(idx))


if __name__ == "__main__":
    io_loop = asyncio.get_event_loop()

    ray.init()

    nn_manager = NeuralNetworkManager.remote()

    object_detection = ObjectDetection("ssd_mobilenet_v1_coco_11_06_2017")
    ray.get(nn_manager.register_model.remote("ObjectDetection", object_detection))

    driver = AnalyzerDriver(io_loop, ["nats://localhost:4222"], nn_manager)
    io_loop.run_until_complete(asyncio.wait([driver.start()]))
    io_loop.run_forever()
    io_loop.close()

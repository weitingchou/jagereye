import ray
import os
from collections import deque

import tasks

from jagereye.streaming import VideoStreamWriter
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
                 src_reader,
                 roi,
                 triggers,
                 nn_manager,
                 motion_threshold,
                 detect_threshold,
                 fps,
                 event_video_format,
                 event_video_margin):
        # TODO: detect_in_region() should be modified to process this
        #       roi format
        self._src_reader = src_reader
        self._roi = (roi[0]["x"], roi[0]["y"], roi[1]["x"], roi[1]["y"])
        self._triggers = triggers
        self._motion_threshold = motion_threshold or 80
        self._detect_threshold = detect_threshold or 0.25
        self._category_index = load_category_index("./coco.labels")
        self._nn_manager = nn_manager
        self._state = STATE["NORMAL"]

        sink_options = {
            "out_dir": "./",
            "video_format": event_video_format or "avi",
            "fps": fps or 15,
            "margin": event_video_margin or 3
        }
        self._video_out = VideoMarginWriterClient(**sink_options)
        logging.info("IntrusionDetectionActor has been created"
                     "(roi: {}, triggers: {}, motion_threshold: {}, "
                     "detect_threshold: {})".format(self._roi,
                                                    self._triggers,
                                                    self._motion_threshold,
                                                    self._detect_threshold))

    def configure(self, params):
        logging.info("Configuring IntrusionDetectionActor, params: {}"
                     .format(params))
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
        detect = ray.get(self._nn_manager.run_model.remote(
            "ObjectDetection",
            [frames[idx]
             for idx in motion]))
        catched = tasks.detect_in_region(self._frame_size["height"],
                                         self._frame_size["width"],
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
                size = (self._frame_size["width"],
                        self._frame_size["height"])
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

    def run(self, frames):
        height, width, _ = frames[0]["image"].shape
        self._frame_size = {"height": height, "width": width}
        motion, detect, catched = self._run_pipeline(frames)
        self._process_event(catched, frames)
        print(catched)
        """
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

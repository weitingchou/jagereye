import ray
import asyncio
import threading
import collections
import cv2
from multiprocessing import Process

from pipelines import IntrusionDetectionActor

from jagereye.api import APIConnector
from jagereye.neural_network.nn_manager import NeuralNetworkManager
from jagereye.neural_network.models import ObjectDetection
from jagereye.streaming import VideoStreamReader
from jagereye.util import logging
import jagereye.streaming.streaming as streaming


ANALYZER_STATUS_CREATED = "created"
ANALYZER_STATUS_RUNNING = "running"
ANALYZER_STATUS_SRC_DOWN = "source_down"
ANALYZER_STATUS_STOPPED = "stopped"

RETCODE = {
    "SUCCESS": 0,
    "SOURCE_DOWN": 1
}


class SourceConnectionError(Exception):
    pass


def kill_process(p):
    """Kill a process.

    Args:
        p: The process to kill.

    Returns:
        True if the process was killed successfully and false otherwise.
    """
    logging.info("Killing process: {}".format(p.pid))
    if p.poll() is not None:
        # The process has already terminated.
        return True

    # Allow the process one second to exit gracefully.
    p.terminate()
    timer = threading.Timer(1, lambda p: p.kill(), [p])
    try:
        timer.start()
        p.wait()
    finally:
        timer.cancel()

    # If the process did not exit within one second, force kill it.
    if p.poll() is not None:
        return True

    # The process was not killed for some reason.
    return False


@ray.remote
class Analyzer(object):
    def __init__(self, sid, name, source, pipelines, nn_manager):
        self._sid = sid
        self._name = name
        self._batch_size = 5
        self._nn_manager = nn_manager

        self._source = source
        self._src_reader = VideoStreamReader.remote()

        self._pipelines = []
        for p in self._pipelines:
            self._add_pipeline(p)

        self._driver = None
        self._status = ANALYZER_STATUS_CREATED

    def _add_pipeline(self, pipeline):
        if pipeline["type"] == "IntrusionDetection":
            params = pipeline["params"]
            self._pipelines.append(
                IntrusionDetectionActor.remote(
                    params["roi"],
                    params["triggers"],
                    self._nn_manager,
                    None,
                    None,
                    None,
                    None,
                    None))

    def get_status(self):
        return self._status

    def _start_source(self):
        ret = ray.get(self._src_reader.open.remote(self._source["url"]))
        if ret != streaming.RETCODE["SUCCESS"]:
            raise SourceConnectionError("Failed to open source '{}'"
                                        .format(self._source["url"]))

    def _release_source(self):
        ray.wait([self._src_reader.release.remote()])
        self._source = None

    def _start_driver(self):
        self._driver = Process(target=self.drive)
        self._driver.daemon = True
        self._driver.start()

    def _stop_driver(self):
        if not kill_process(self._driver):
            logging.error("Failed to kill driver process for some unknown"
                          " reason.")
        self._driver = None

    def start(self):
        if self._status != ANALYZER_STATUS_RUNNING:
            try:
                self._start_source()
            except SourceConnectionError:
                self._status = ANALYZER_STATUS_SRC_DOWN
                return RETCODE["SOURCE_DOWN"]
            else:
                # self._start_driver()
                self._status = ANALYZER_STATUS_RUNNING
        return RETCODE["SUCCESS"]

    def stop(self):
        # self._stop_driver()
        self._release_source()

    def drive(self):
        logging.info("Starts running Analyzer: {}".format(self._sid))

        end_of_video = False
        while True:
            frames = self._src_reader.read.remote(self._batch_size)
            ret, images = ray.get(frames)
            if ret == streaming.RETCODE["CONNECTION_BROKEN"]:
                # self._exception = SourceConnectionError()
                # TODO: we should try to reconnect the source
                logging.error("Source connection broken")
                break
            elif ret == streaming.RETCODE["EOF"]:
                end_of_video = True

            tasks = [p.run.remote(frames) for p in self._pipelines]
            # We will wait until all tasks finished
            ray.wait(tasks, num_returns=len(tasks))

            if end_of_video:
                break
        logging.info("Analyzer terminated: {}".format(self._sid))


class AnalyzerManager(APIConnector):
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
        self._analyzers = collections.defaultdict(lambda: {})

    def _create_worker(self, sid, name, source, pipelines):
        if "worker" not in self._analyzers[sid]:
            self._analyzers[sid]["worker"] = Analyzer.remote(
                sid,
                name,
                source,
                pipelines,
                self._nn_manager)

    def on_create(self, params):
        logging.info("Creating Analyzer, params: {}".format(params))
        try:
            sid = params["id"]
            name = params["name"]
            source = params["source"]
            pipelines = params["pipelines"]

            self._analyzers[sid]["name"] = name
            self._analyzers[sid]["source"] = source
            self._analyzers[sid]["pipelines"] = pipelines

            self._create_worker(sid, name, source, pipelines)

            # Start analyzer
            ret = ray.get(self._analyzers[sid]["worker"].start.remote())
            if ret != RETCODE["SUCCESS"]:
                logging.error("Failed to start analyzer: {}".format(sid))
                raise RuntimeError("Failed to start analyzer with params: {}"
                                   .format(params))
        except KeyError as e:
            raise RuntimeError("Invalid request format: {}".format(str(e)))
        except Exception as e:
            logging.error(e)

    def _get_worker_status(self, sid):
        if sid not in self._analyzers:
            raise RuntimeError("Analyzer not found: {}".format(sid))
        if "worker" not in self._analyzers[sid]:
            return ANALYZER_STATUS_STOPPED
        return ray.get(self._analyzers[sid]["worker"].get_status.remote())

    def on_read(self, params):
        logging.info("Getting Analyzer information, params: {}".format(params))

        if isinstance(params, list):
            result = dict()
            for sid in params:
                result[sid] = self._get_worker_status(sid)
        else:
            # TODO: check if params is an ObjectID
            result = self._get_worker_status(params)
        return result

    def on_update(self, params):
        logging.info("Updating Analyzer, params: {}".format(params))
        try:
            sid = params["id"]
            content = params["params"]
        except KeyError as e:
            if e.args[0] == 'id':
                raise RuntimeError("Invalid request format: "
                                   "missing field 'id'.")
            elif e.args[0] == 'params':
                raise RuntimeError("Invalid request format: "
                                   "missing field 'params'.")
        else:
            if sid not in self._analyzers:
                raise RuntimeError("Analyzer not found")

            if "worker" in self._analyzers[sid]:
                raise RuntimeError("Hot re-configuring analyzer is not "
                                   "allowed, please stop analyzer first "
                                   "before updating it.")

            analyzer = self._analyzers[sid]
            if "name" in content:
                analyzer["name"] = content["name"]
            if "source" in content:
                analyzer["source"] = content["source"]
            if "pipelines" in content:
                analyzer["pipelines"] = content["pipelines"]

            self._create_worker(sid,
                                analyzer["name"],
                                analyzer["source"],
                                analyzer["pipelines"])

            ret = ray.get(analyzer["worker"].start.remote())
            if ret != RETCODE["SUCCESS"]:
                logging.error("Failed to start analyzer: {}".format(sid))
                raise RuntimeError("Failed to start analyzer: {}"
                                   .format(sid))
            return self._get_worker_status(sid)

    def _delete_analyzer(self, sid):
        ray.wait([self._analyzers[sid]["worker"].stop.remote()])
        del self._analyzers[sid]

    def on_delete(self, params):
        logging.info("Deleting Analyzer: {}".format(params))
        try:
            # TODO: Need to make sure the allocated resources for
            #       analyzer "sid" also been deleted completely
            if isinstance(params, list):
                for sid in params:
                    self._delete_analyzer(sid)
            else:
                sid = params
                self._delete_analyzer(sid)
        except KeyError:
            raise RuntimeError("Invalid request foramt")

    def on_start(self, sid):
        logging.info("Starting Analyzer: {}".format(sid))
        if sid not in self._analyzers:
            raise RuntimeError("Analyzer not found")
        else:
            analyzer = self._analyzers[sid]
            self._create_worker(sid,
                                analyzer["name"],
                                analyzer["source"],
                                analyzer["pipelines"])
            ret = ray.get(analyzer["worker"].start.remote())
            if ret != RETCODE["SUCCESS"]:
                logging.error("Failed to start analyzer: {}".format(sid))
                raise RuntimeError("Failed to start analyzer: {}"
                                   .format(sid))

    def _stop_worker(self, sid):
        if "worker" in self._analyzers[sid]:
            ray.wait([self._analyzers[sid]["worker"].stop.remote()])
            del self._analyzers[sid]["worker"]

    def on_stop(self, sid):
        logging.info("Stopping Analyzer: {}".format(sid))
        if sid not in self._analyzers:
            raise RuntimeError("Analyzer not found")
        else:
            self._stop_worker(sid)


if __name__ == "__main__":
    io_loop = asyncio.get_event_loop()

    ray.init()

    nn_manager = NeuralNetworkManager.remote()

    object_detection = ObjectDetection("ssd_mobilenet_v1_coco_11_06_2017")
    ray.get(nn_manager.register_model.remote("ObjectDetection", object_detection))

    manager = AnalyzerManager(io_loop, ["nats://localhost:4222"], nn_manager)
    io_loop.run_forever()
    io_loop.close()

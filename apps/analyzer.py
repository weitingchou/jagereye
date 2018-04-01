from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import asyncio
import time
from dask.distributed import Client
from multiprocessing import Process, Pipe, TimeoutError

from intrusion_detection import IntrusionDetector

from jagereye import video_proc as vp
from jagereye.api import APIConnector
from jagereye.streaming import VideoStreamReader, ConnectionBrokenError
from jagereye import logging


class HotReconfigurationError(Exception):
    def __str__(self):
        return ("Hot re-configuring analyzer is not allowed, please"
                " stop analyzer first before updating it.")


def check_source_connection(url):
    """Check whether the source url is good.

    Raises:
        ConnectionBrokenError: Raises if VideoStreamReader can't open the
            provided url.
    """
    # XXX: The function will cause an error under MacOSX, for more detail
    # please see
    # "https://stackoverflow.com/questions/16254191/python-rpy2-and-matplotlib-conflict-when-using-multiprocessing"
    reader = VideoStreamReader()
    try:
        reader.open(url, only_validate=True)
    except ConnectionBrokenError:
        raise
    finally:
        reader.release()


def create_pipeline(pipelines, frame_size):
    result = []
    for p in pipelines:
        if p["type"] == "IntrusionDetection":
            params = p["params"]
            result.append(IntrusionDetector(
                params["roi"],
                params["triggers"],
                frame_size))
    return result


class Driver(object):
    def __init__(self):
        self._driver_process = None
        self._sig_parent = None
        self._sig_child = None

    def start(self, func, *argv):
        self._sig_parent, self._sig_child = Pipe()
        self._driver_process = Process(
            target=Driver.run_driver_func,
            args=(func,
                  self._sig_child,
                  argv))
        self._driver_process.daemon = True
        self._driver_process.start()

    def terminate(self, timeout=5):
        assert self._driver_process is not None, "It's an error to attempt to \
            terminate a driver before it has been started."
        try:
            self._driver_process.join(timeout)
        except TimeoutError:
            logging.error("The driver was not terminated for some reason "
                          "(exitcode: {}), force to terminate it."
                          .format(self._driver_process.exitcode))
            self._driver_process.terminate()
            time.sleep(0.1)
        finally:
            self._sig_parent.close()
            self._sig_parent = None
            self._sig_child = None
            self._driver_process = None

    def poll(self, timeout=None):
        if timeout is not None:
            return self._sig_parent.poll(timeout)
        else:
            return self._sig_parent.poll()

    def send(self, msg):
        self._sig_parent.send(msg)

    def recv(self):
        return self._sig_parent.recv()

    @staticmethod
    def run_driver_func(driver_func, signal, *argv):
        try:
            driver_func(signal, *argv[0])
        finally:
            signal.close()


class Analyzer():

    STATUS_CREATED = "created"
    STATUS_RUNNING = "running"
    STATUS_SRC_DOWN = "source_down"
    STATUS_STOPPED = "stopped"

    def __init__(self, name, source, pipelines):
        self._status = Analyzer.STATUS_CREATED
        self._name = name
        self._source = source
        self._pipelines = pipelines
        self._driver = Driver()

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if self._status == Analyzer.STATUS_RUNNING:
            raise HotReconfigurationError()
        self._name = value

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        if self._status == Analyzer.STATUS_RUNNING:
            raise HotReconfigurationError()
        self._source = value

    @property
    def pipelines(self):
        return self._pipelines

    @pipelines.setter
    def pipelines(self, value):
        if self._status == Analyzer.STATUS_RUNNING:
            raise HotReconfigurationError()
        self._pipelines = value

    def get_status(self):
        if self._driver.poll() and self._driver.recv() == "source_down":
            self._status = Analyzer.STATUS_SRC_DOWN
        return self._status

    def start(self):
        if self._status != Analyzer.STATUS_RUNNING:
            self._driver.start(Analyzer.run,
                               self._name,
                               self._source,
                               self._pipelines)
            self._status = Analyzer.STATUS_RUNNING

    def stop(self):
        if self._status == Analyzer.STATUS_RUNNING:
            self._driver.send("stop")
            self._driver.terminate()
            self._status = Analyzer.STATUS_STOPPED

    @staticmethod
    def run(signal, name, source, pipelines):
        logging.info("Starts running Analyzer: {}".format(name))
        try:
            # TODO: Get the address of scheduler from the configuration
            #       file.
            c = Client("127.0.0.1:8786")

            src_reader = VideoStreamReader()
            src_reader.open(source["url"])
            video_info = src_reader.get_video_info()

            pipelines = create_pipeline(pipelines,
                                        video_info["frame_size"])

            while True:
                frames = src_reader.read(batch_size=5)
                motion = vp.detect_motion(frames)

                for p in pipelines:
                    p.run(frames, motion)

                if signal.poll() and signal.recv() == "stop":
                    break
        except ConnectionBrokenError:
            logging.error("Error occurred when trying to connect to source {}"
                          .format(source["url"]))
            # TODO: Should push a notifcation of this error
            signal.send("source_down")
        finally:
            src_reader.release()
            for p in pipelines:
                p.release()
            c.close()
            logging.info("Analyzer terminated: {}".format(name))


class AnalyzerManager(APIConnector):
    def __init__(self, io_loop, nats_hosts=None):
        super().__init__("analyzer", io_loop, nats_hosts)
        self._analyzers = dict()

    def on_create(self, params):
        logging.info("Creating Analyzer, params: {}".format(params))
        try:
            sid = params["id"]
            name = params["name"]
            source = params["source"]
            pipelines = params["pipelines"]

            check_source_connection(source["url"])

            # Create analyzer object
            self._analyzers[sid] = Analyzer(
                name, source, pipelines)

            # Start analyzer
            self._analyzers[sid].start()
        except KeyError as e:
            raise RuntimeError("Invalid request format: {}".format(e.args[0]))
        except ConnectionBrokenError:
            raise RuntimeError("Failed to establish connection to {}"
                               .format(source["url"]))
        except Exception as e:
            logging.error(e)

    def _get_analyzer_status(self, sid):
        if sid not in self._analyzers:
            raise RuntimeError("Analyzer not found: {}".format(sid))
        return self._analyzers[sid].get_status()

    def on_read(self, params):
        logging.info("Getting Analyzer information, params: {}".format(params))

        if isinstance(params, list):
            result = dict()
            for sid in params:
                result[sid] = self._get_analyzer_status(sid)
        else:
            # TODO: check if params is an ObjectID
            result = self._get_analyzer_status(params)
        return result

    def on_update(self, update):
        logging.info("Updating Analyzer, params: {}".format(update))
        try:
            sid = update["id"]
            params = update["params"]
            analyzer = self._analyzers[sid]
            if "name" in params:
                analyzer.name = params["name"]
            if "source" in params:
                analyzer.source = params["source"]
            if "pipelines" in params:
                analyzer.pipelines = params["pipelines"]
        except KeyError as e:
            raise RuntimeError("Invalid request format: missing "
                               "field '{}'.".format(e.args[0]))
        except HotReconfigurationError as e:
            raise RuntimeError(str(e))

    def _delete_analyzer(self, sid):
        self._analyzers[sid].stop()
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
            try:
                check_source_connection(analyzer.source["url"])
            except ConnectionBrokenError:
                raise RuntimeError("Failed to establish connection to {}"
                                   .format(analyzer.source["url"]))
            else:
                analyzer.start()

    def on_stop(self, sid):
        logging.info("Stopping Analyzer: {}".format(sid))
        if sid not in self._analyzers:
            raise RuntimeError("Analyzer not found")
        else:
            self._analyzers[sid].stop()


if __name__ == "__main__":
    io_loop = asyncio.get_event_loop()

    manager = AnalyzerManager(io_loop, ["nats://localhost:4222"])
    io_loop.run_forever()
    io_loop.close()

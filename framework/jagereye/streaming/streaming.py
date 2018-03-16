from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import time
import threading
from collections import deque
from urllib.parse import urlparse

import cv2
import ray
import numpy as np

from jagereye.util import logging


DEFAULT_STREAM_BUFFER_SIZE = 64     # frames
DEFAULT_FPS = 15
RETCODE = {
    "SUCCESS": 0,
    "ALREADY_OPENED": 1,
    "FAILED_TO_OPEN": 2,
    "CONNECTION_BROKEN": 3,
    "EOF": 4
}


def _is_live_stream(url):
    """Check whether the source is live stream or not.

    Currently we only support "RTSP" as live streaming.

    Returns:
        boolean
    """
    return urlparse(url).scheme.lower() == "rtsp"


class StreamNotOpenError(Exception):
    pass


class ConnectionBrokenError(Exception):
    pass


class EndOfVideoError(Exception):
    pass


class StreamReaderThread(threading.Thread):
    def __init__(self,
                 reader,
                 queue,
                 stop_event,
                 cap_interval,
                 is_live_stream):
        super(StreamReaderThread, self).__init__()
        self._reader = reader
        self._queue = queue
        self._stop_event = stop_event
        self._cap_interval = cap_interval / 1000.0
        self._is_live_stream = is_live_stream
        self._exception = None

    def run(self):
        try:
            while not self._stop_event.is_set():
                success, image = self._reader.read()
                if not success:
                    if self._is_live_stream:
                        raise ConnectionBrokenError()
                    else:
                        raise EndOfVideoError()
                timestamp = np.array(time.time())
                self._queue.appendleft({
                    "image": image,
                    "timestamp": timestamp
                })
                time.sleep(self._cap_interval)
            logging.info("Reader thread is terminated")
        except Exception as e:
            self._exception = e

    def get_exception(self):
        return self._exception


@ray.remote
class VideoStreamReader(object):
    """The video stream reader.

    The reader to read frames from a video stream. The video stream can be a
    video file or a live stream such as RTSP, Motion JPEG. Each captured blob
    has a "image" tensor that stores the read image and a "timestamp" tensor
    that stores the timestamp of the image.

    The "image" tensor is a 3-dimensional numpy `ndarray` whose type is uint8
    and the shape format is:
    1. Image height.
    2. Image width.
    3. Number of channels, which is usually 3.

    The "timestamp" tensor is a 0-dimensional numpy `ndarray` whose type is
    string.
    """

    def __init__(self, buffer_size=DEFAULT_STREAM_BUFFER_SIZE):
        """Initialize a `VideoStreamReader` object.

        Args:
          src (str): The video source. It can be a video file name, or live
            stream URL such as RTSP, Motion JPEG.
        """
        self._reader = cv2.VideoCapture()
        self._queue = deque(maxlen=DEFAULT_STREAM_BUFFER_SIZE)
        self._stop_event = threading.Event()
        self._current_source = None
        self._thread = None
        self._is_live_stream = False
        self._capture_interval = None

    def _start_reader_thread(self):
        logging.info("Starting reader thread")
        if not self._reader.isOpened():
            raise RuntimeError("Stream not opened")
        self._thread = StreamReaderThread(self._reader,
                                          self._queue,
                                          self._stop_event,
                                          self._capture_interval,
                                          self._is_live_stream)
        self._thread.daemon = True
        self._thread.start()

    def open(self, src, fps=DEFAULT_FPS):
        if self._current_source is not None:
            return RETCODE["ALREADY_OPENED"]

        if not self._reader.open(src):
            logging.error("Can't open video stream '{}'".format(src))
            return RETCODE["FAILED_TO_OPEN"]

        self._stop_event.clear()
        self._is_live_stream = _is_live_stream(src)
        self._capture_interval = 1000.0 / fps
        self._current_source = src
        self._start_reader_thread()
        return RETCODE["SUCCESS"]

    def release(self):
        self._stop_event.set()
        self._thread = None
        self._reader.release()
        self._queue.clear()
        self._current_source = None

    def _read_all(self):
        return [self._queue.pop() for _ in range(len(self._queue))]

    def _read(self, batch_size):
        return [self._queue.pop() for _ in range(batch_size)]

    def read(self, batch_size=1):
        """The routine of video stream capturer capturation.

        Returns:
          `Blob`: The blob which contains "image" and "timestamp" tensor.

        Raises:
          RuntimeError: If the stream is live and disconnected temporarily.
          ValueError: If the stream ends.
        """
        retcode = RETCODE["SUCCESS"]
        data = []
        cur_q_size = len(self._queue)
        while cur_q_size < batch_size:
            if self._thread.get_exception() is not None:
                break
            time.sleep(0.1)
            cur_q_size = len(self._queue)

        exception = self._thread.get_exception()
        if isinstance(exception, EndOfVideoError):
            if cur_q_size <= batch_size:
                data = self._read_all()
                retcode = RETCODE["EOF"]
            else:
                data = self._read(batch_size)
        elif isinstance(exception, ConnectionBrokenError):
            retcode = RETCODE["CONNECTION_BROKEN"]
        else:
            # XXX: In this case we are assuming that everything is fine,
            #      and current queue size should creater than the batch
            #      size.
            data = self._read(batch_size)
        return retcode, data


@ray.remote
class VideoStreamWriter(object):
    def __init__(self):
        self._writer = cv2.VideoWriter()

    def open(self, path, video_format, fps, size):
        if self._writer.isOpened():
            return RETCODE["ALREADY_OPENED"]
        filename = "{}.{}".format(path, video_format)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        if not self._writer.open(filename, fourcc, fps, size):
            return RETCODE["FAILED_TO_OPEN"]
        return RETCODE["SUCCESS"]

    def write(self, frames):
        if isinstance(frames, list):
            for frame in frames:
                self._writer.write(frame["image"])
        else:
            self._writer.write(frames["image"])

    def end(self):
        self._writer.release()

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from collections import deque
from enum import Enum

import cv2
from dask.distributed import get_client

from jagereye import video_proc as vp
from jagereye import gpu_worker
from jagereye.streaming import VideoStreamWriter
from jagereye import logging


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


class VideoMarginWriter(object):
    def __init__(self, out_dir, video_format, fps, margin):
        self._writer = VideoStreamWriter()
        self._out_dir = out_dir
        self._video_format = video_format
        self._fps = fps

        self._max_margin_in_frames = self._fps * margin
        self._back_margin_q = deque(maxlen=self._max_margin_in_frames)
        self._front_margin_counter = 0

    def open(self, filename, size):
        if not isinstance(filename, str):
            filename = "{}".format(filename)
        filepath = os.path.join(self._out_dir, filename)
        try:
            self._writer.open(filepath,
                              self._video_format,
                              self._fps,
                              size)
        except RuntimeError as e:
            logging.error(str(e))
            raise
        for _ in range(len(self._back_margin_q)):
            self._writer.write(self._back_margin_q.popleft())

    def append_back_margin_queue(self, frames):
        for f in frames:
            self._back_margin_q.append(f)

    def clear_back_margin_queue(self):
        self._back_margin_q.clear()

    def reset_front_margin(self):
        self._front_margin_counter = 0

    def write(self, frames):
        self._writer.write(frames)
        self._front_margin_counter += len(frames)
        if self._front_margin_counter >= self._max_margin_in_frames:
            self._writer.end()
            self.reset_front_margin()
            raise EndOfMarginError()

    def end(self):
        self._writer.end()
        self.clear_back_margin_queue()
        self.reset_front_margin()


class IntrusionDetector(object):

    STATE = Enum("State", "NORMAL ALERTING")

    def __init__(self,
                 roi,
                 triggers,
                 frame_size,
                 detect_threshold=0.25,
                 fps=15,
                 event_video_format="avi",
                 event_video_margin=3):
        try:
            # Get Dask client
            self._client = get_client()
        except ValueError:
            raise RuntimeError("Should connect to Dask scheduler before"
                               " initialzing this object")

        # TODO: detect_in_roi() should be modified to be abled to process this
        #       roi format
        self._roi = (roi[0]["x"], roi[0]["y"], roi[1]["x"], roi[1]["y"])
        self._triggers = triggers
        self._frame_size = frame_size
        self._detect_threshold = detect_threshold
        self._category_index = load_category_index("./coco.labels")
        self._state = IntrusionDetector.STATE.NORMAL

        sink_options = {
            "out_dir": "./",
            "video_format": event_video_format,
            "fps": fps,
            "margin": event_video_margin
        }
        self._video_out = VideoMarginWriter(**sink_options)
        logging.info("IntrusionDetector has been created"
                     "(roi: {}, triggers: {}, detect_threshold: {})".format(
                         self._roi,
                         self._triggers,
                         self._detect_threshold))

    def _check_intrusion(self, candidates):
        """Check if the detected objects will trigger an intrusion event.

        Args:
            candidates: A list of object detection result objects, each a
                object of format (bboxes, scores, classes, num_detctions).

        Returns:
            A list of tuple list that specifies the triggered candidates,
            each a tuple list of format [(label, detect_index), ...].
        """
        width, height = self._frame_size
        r_xmin, r_ymin, r_xmax, r_ymax = self._roi
        results = []
        for i in range(len(candidates)):
            (bboxes, scores, classes, num_candidates) = candidates[i]

            in_roi_labels = []
            for j in range(int(num_candidates[0])):
                # Check if score passes the threshold.
                if scores[0][j] < self._detect_threshold:
                    continue
                # Check if the object in in the trigger list.
                # XXX: Is it posssible to generate index that is not in the
                #      category_index list?
                try:
                    label = self._category_index[int(classes[0][j])]
                except KeyError:
                    continue
                else:
                    if label not in self._triggers:
                        continue
                # Check whether the object is in roi or not.
                o_ymin, o_xmin, o_ymax, o_xmax = bboxes[0][j]
                o_xmin, o_ymin, o_xmax, o_ymax = (o_xmin * width, o_ymin * height,
                                                  o_xmax * width, o_ymax * height)
                overlap_roi = max(0.0, min(o_xmax, r_xmax) - max(o_xmin, r_xmin)) \
                    * max(0.0, min(o_ymax, r_ymax) - max(o_ymin, r_ymin))
                if overlap_roi > 0.0:
                    in_roi_labels.append((label, j))
            results.append(in_roi_labels)
        return results

    def _process_event(self, catched, frames):
        self._video_out.append_back_margin_queue(frames)
        if self._state == IntrusionDetector.STATE.NORMAL:
            if any(catched):
                try:
                    timestamp = frames[0].timestamp
                    self._video_out.open(timestamp, self._frame_size)
                    logging.info("Creating event video: {}".format(timestamp))
                except RuntimeError as e:
                    logging.error(e)
                    raise
                self._state = IntrusionDetector.STATE.ALERTING
        elif self._state == IntrusionDetector.STATE.ALERTING:
            if any(catched):
                self._video_out.reset_front_margin()
            try:
                self._video_out.write(frames)
            except EndOfMarginError:
                logging.info("End of event video")
                self._state = IntrusionDetector.STATE.NORMAL
        else:
            assert False, "Unknown state: {}".format(self._state)

    def run(self, frames, motion):
        f_motion = self._client.scatter(motion)
        detect = self._client.submit(gpu_worker.run_model,
                                     "object_detection",
                                     f_motion,
                                     resources={"GPU": 1})
        catched = self._check_intrusion(detect.result())
        self._process_event(catched, frames)

        drawn_images = []
        if any(catched):
            drawn_images = [vp.draw_region(
                frame,
                self._roi,
                (66, 194, 244))
                for frame in frames]
        else:
            drawn_images = [vp.draw_region(
                frame,
                self._roi,
                (226, 137, 59))
                for frame in frames]
        for image in drawn_images:
            cv2.imshow("frame", image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    def release(self):
        self._video_out.end()
        self._state = IntrusionDetector.STATE.NORMAL

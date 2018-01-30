"""The modules used by tripwire worker."""

import json
import threading
import os
from queue import Queue

import cv2
import numpy as np
import tensorflow as tf

from jagereye.streaming import IModule
from jagereye.util import logging


class _ModeEnum(object):
    """Enum for modes."""
    NORMAL = 0
    ALERT_START = 1
    ALERTING = 2
    ALERT_END = 3

_MODE = _ModeEnum()


class MotionDetectionModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for motion detection."""

    def __init__(self, sensitivity=80):
        """Create a new `MotionDetectionModule`

        Args:
          sensitivity (int): The sensitivity of motion detection, range from 1
            to 100. Defaults to 80.
        """
        sensitivity_clamp = max(1, min(sensitivity, 100))
        self._threshold = (100 - sensitivity_clamp) * 0.05
        self._last_gray_image = None

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of motion detection module execution.

        Raises:
            RuntimeError: If the input tensor is not 3-dimensional.
        """
        # TODO(JiaKuan Su): Currently, I only handle the case for batch_size=1,
        # please help complete the case for batch_size>1.
        blob = blobs[0]
        image = blob.fetch('image')
        if image.ndim != 3:
            raise RuntimeError('The input "image" tensor is not 3-dimensional.')

        cur_gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        moved = False

        if not self._last_gray_image is None:
            # Get the difference of two grayscale images.
            res = cv2.absdiff(self._last_gray_image, cur_gray_image)
            # Remove the noise and do the threshold.
            res = cv2.blur(res, (5, 5))
            res = cv2.morphologyEx(res, cv2.MORPH_OPEN, None)
            res = cv2.morphologyEx(res, cv2.MORPH_CLOSE, None)
            ret, res = cv2.threshold(res, 10, 255, cv2.THRESH_BINARY_INV) #pylint: disable=unused-variable
            # Count the number of black pixels.
            num_black = np.count_nonzero(res == 0)
            # Calculate the image size.
            im_size = image.shape[1] * image.shape[0]
            # Calculate the average of black pixel in the image.
            avg_black = (num_black * 100.0) / im_size
            # Detect moving by testing whether the average of black exceeds the
            # threshold or not.
            moved = avg_black >= self._threshold
            blob.feed('res', res)

        self._last_gray_image = cur_gray_image
        blob.feed('moved', np.array(moved))

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        pass


class ObjectDetectionModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for object detection."""

    def __init__(self, ckpt_path):
        """Create a new `ObjectDetectionModule`

        Args:
          ckpt_path (string): The path to the TensorFlow model file (.pb file).
        """
        # Path to frozen detection graph.
        self._ckpt_path = ckpt_path
        # The TensorFlow graph.
        self._detection_graph = None
        # The TensorFlow session.
        self._sess = None

    def prepare(self):
        """The routine of object detection module preparation to create a
        TensorFlow graph and session."""
        # Load a model into memory
        self._detection_graph = tf.Graph()
        with self._detection_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(self._ckpt_path, 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')
            with tf.Session(graph=self._detection_graph) as sess:
                self._sess = sess

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of object detection module execution to execute.

        Raises:
            RuntimeError: If the input tensor is not 3-dimensional.
        """
        # Definite input and output Tensors for detection_graph
        image_tensor = self._get_tensor('image_tensor:0')
        # Each box represents a part of the image where a particular object was
        # detected.
        detection_boxes = self._get_tensor('detection_boxes:0')
        # Each score represent how level of confidence for each of the objects.
        # Score is shown on the result image, together with the class label.
        detection_scores = self._get_tensor('detection_scores:0')
        detection_classes = self._get_tensor('detection_classes:0')
        num_detections = self._get_tensor('num_detections:0')
        for blob in blobs:
            image = blob.fetch('image')
            if image.ndim != 3:
                raise RuntimeError('The input "image" tensor is not '
                                   '3-dimensional.')
            moved = bool(blob.fetch('moved'))

            if not moved:
                boxes = np.array([[]])
                scores = np.array([[]])
                classes = np.array([[]])
                num = np.array([0.0])
            else:
                # Expand dimensions since the model expects images to have
                # shape: [1, None, None, 3]
                image_expanded = np.expand_dims(image, axis=0)
                # Actual detection.
                fetches = [detection_boxes,
                           detection_scores,
                           detection_classes,
                           num_detections]
                feed_dict = {image_tensor: image_expanded}
                (boxes, scores, classes, num) = \
                    self._sess.run(fetches, feed_dict=feed_dict)
            blob.feed('detection_boxes', boxes)
            blob.feed('detection_scores', scores)
            blob.feed('detection_classes', classes)
            blob.feed('num_detections', num)

        return blobs

    def destroy(self):
        """The routine of object detection module destruction."""
        pass

    def _get_tensor(self, name):
        """Get a tensor from the graph.

        Args:
          name (string): The tensor name to get.

        Returnes:
          tensorflow `Tensor`: The tensor to get.
        """
        return self._detection_graph.get_tensor_by_name(name)


class InRegionDetectionModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for detecting in-region objects."""

    def __init__(self,
                 category_index,
                 region,
                 triggers,
                 min_score_thresh=0.25):
        """Create a new `InRegionDetectionModule`.

        Args:
          category_index (dict): The labels category index.
          triggers (list of string): The interested object labels to trigger.
          region (tuple): Range of the region. The tuple contains:
            xmin (int): The left position.
            ymin (int): The top position.
            xmax (int): The right position.
            ymax (int): The bottom position.
          min_score_thresh (float): The minimum threshold of score to detect.
        """
        self._category_index = category_index
        self._triggers = triggers
        self._region = region
        self._min_score_thresh = min_score_thresh

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of module execution."""
        for blob in blobs:
            image = blob.fetch('image')
            im_width = image.shape[1]
            im_height = image.shape[0]
            boxes = np.squeeze(blob.fetch('detection_boxes'))
            scores = np.squeeze(blob.fetch('detection_scores'))
            classes = np.squeeze(blob.fetch('detection_classes'))
            num = int(blob.fetch('num_detections')[0])
            result = self._detect_in_region_objects(boxes,
                                                    scores,
                                                    classes,
                                                    num,
                                                    im_width,
                                                    im_height)

            blob.feed('region', np.array(self._region))
            blob.feed('labels', result[0])
            blob.feed('boxes', result[1])
            blob.feed('scores', result[2])

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        pass

    def _is_in_region(self, box):
        """Test whether a bounding box is in region or not.

        Args:
          box (tuple): Range of the region. The tuple contains:
            xmin (int): The left position.
            ymin (int): The top position.
            xmax (int): The right position.
            ymax (int): The bottom position.

        Returns:
          bool: True if the bounding box is in region, False otherwise.
        """
        (o_xmin, o_ymin, o_xmax, o_ymax) = (box[0], box[1], box[2], box[3])
        (r_xmin, r_ymin, r_xmax, r_ymax) = (self._region[0], self._region[1],
                                            self._region[2], self._region[3])
        overlap_region = max(0.0, min(o_xmax, r_xmax) - max(o_xmin, r_xmin)) \
                         * max(0.0, min(o_ymax, r_ymax) - max(o_ymin, r_ymin))
        return overlap_region > 0.0

    def _detect_in_region_objects(self,
                                  boxes,
                                  scores,
                                  classes,
                                  num,
                                  im_width,
                                  im_height):
        """Detect objects that are in the region.

        Args:
          boxes (numpy `ndarray`): The bounding boxes of objects.
          scores (numpy `ndarray`): The scores of objects.
          classes (numpy `ndarray`): The classes of objects.
          num (int): The number of objects.
          im_width (int): The image width.
          im_height (int): The image height.

        Returns:
          tuple: The detection result. The tuple contains:
            in_region_labels (numpy `ndarray`): The labels of objects that are
              in the region.
            in_region_boxes (numpy `ndarray`): The bounding boxes of objects
              that are in the region.
            in_region_scores (numpy `ndarray`): The scores of objects that are
              in the region.
        """
        in_region_labels = []
        in_region_boxes = []
        in_region_scores = []

        for i in range(num):
            # Check its label is interested or not.
            class_id = int(classes[i])
            if not class_id in self._category_index:
                continue
            label = self._category_index[class_id]
            if not label in self._triggers:
                continue
            # Check score is >= threshold.
            score = scores[i]
            if score < self._min_score_thresh:
                continue
            # Check whether the object is in region or not.
            box = boxes[i]
            ymin, xmin, ymax, xmax = box
            unnormalized_box = (xmin * im_width, ymin * im_height,
                                xmax * im_width, ymax * im_height)
            if not self._is_in_region(unnormalized_box):
                continue
            # Put the results.
            in_region_labels.append(label)
            in_region_boxes.append(box)
            in_region_scores.append(score)

        result = (
            np.array(in_region_labels),
            np.array(in_region_boxes),
            np.array(in_region_scores)
        )

        return result


class TripwireModeModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for maintaining the tripwire mode."""

    def __init__(self, reserved_count):
        self._reserved_count = reserved_count
        self._not_detected_counter = 0
        self._mode = _MODE.NORMAL

    def prepare(self):
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Currently, I only handle the case for batch_size=1,
        # please help complete the case for batch_size>1.
        blob = blobs[0]
        in_region_labels = blob.fetch('labels')

        # Mode switch.
        if self._mode == _MODE.NORMAL:
            if in_region_labels.shape[0] > 0:
                self._mode = _MODE.ALERT_START
        elif self._mode == _MODE.ALERT_START:
            self._mode = _MODE.ALERTING
            self._not_detected_counter = 0
        elif self._mode == _MODE.ALERTING:
            if in_region_labels.shape[0] > 0:
                self._not_detected_counter = 0
            else:
                self._not_detected_counter += 1
            if self._not_detected_counter == self._reserved_count:
                self._mode = _MODE.ALERT_END
        elif self._mode == _MODE.ALERT_END:
            self._mode = _MODE.NORMAL

        blob.feed('mode', np.array(self._mode))

        return blobs

    def destroy(self):
        pass


def _record_video(video_name,
                  thumbnail_name,
                  fps,
                  video_size,
                  save_metadata,
                  metadata_name,
                  metadata_frame_names,
                  metadata_custom_obj,
                  queue):
    """Threading function to record a video.

    Args:
      video_name (string): The name of recorded video.
      thumbnail_name (string): The name of thumbnail image.
      fps (int): The FPS of recorded video.
      video_size (tuple): The size of recorded video. The tuple contains:
        width (int): The video width.
        height (int): The video height.
      save_metadata (bool): To store the metadata of the video clip or not.
      metadata_name (string): The name of metadata file, the argument only used
        when save_metadata is True.
      metadata_frame_names (list of string): The names of tensors to store in
        metadata, the argument only used when save_metadata is True.
      metadata_custom_obj (dict): The names and values to store in custom field
        of metadata, the argument only used when save metadata is True.
      queue (`queue.Queue`): The task queue.
    """
    logging.info('Start recording {}'.format(video_name))

    gst_pipeline = ('appsrc ! autovideoconvert ! x264enc ! matroskamux !'
                    ' filesink location={}'.format(video_name))
    video_writer = cv2.VideoWriter(gst_pipeline, 0, fps, video_size)

    if save_metadata:
        metadata = {
            'fps': fps,
            'custom': metadata_custom_obj,
            'frames': []
        }

    while True:
        task = queue.get(block=True)
        command = task['command']
        if command == 'RECORD':
            blob = task['blob']
            image = blob.fetch('image')
            video_writer.write(image)
            if task['thumbnail']:
                cv2.imwrite(thumbnail_name, image)
                logging.info('Save thumbnail {}'.format(thumbnail_name))

            # Update metadata if necessary.
            if save_metadata:
                # Get timestamp
                timestamp = float(blob.fetch('timestamp'))
                # Get per-frame information.
                frame = dict()
                for name in metadata_frame_names:
                    frame[name] = blob.fetch(name).tolist()

                # Update metadata.
                if not 'start' in metadata:
                    metadata['start'] = timestamp
                metadata['end'] = timestamp
                metadata['frames'].append(frame)
        elif command == 'END':
            if save_metadata:
                with open(metadata_name, 'w') as outfile:
                    json.dump(metadata, outfile)
                    logging.info('Save metadata {}'.format(metadata_name))

            break

    video_writer.release()
    logging.info('End recording {}'.format(video_name))


class VideoRecordModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for recording video clips."""

    def __init__(self,
                 files_dir,
                 reserved_count,
                 fps,
                 image_name='image',
                 video_format='mp4',
                 thumbnail_format='jpg',
                 save_metadata=True,
                 metadata_frame_names=[],
                 metadata_custom_names=[]):
        """Create a new `VideoRecordModule`.

        Args:
          files_dir (dict): The directory to store the output video. It has two
            items: "abs" for absolute path, "relative" for realtive path to the
            shared root directory.
          reserved_count (int): The number of reseved images before alert mode.
          fps (int): The FPS of recorded video.
          image_name (string): The name of input tensor to read. Defaults to
            "image".
          video_format (string): The format of video. Defaults to "mp4".
          thumbnail_format (string): The format of thumbnail image. Defaults to
            "mp4".
          save_metadata (bool): To store the metadata of the video clip or not.
            Defaults to True.
          metadata_frame_names (list of string): The names of tensors to store
            in per-frame field of metadata, the argument only used when save
            metadata is True. Defaults to [].
          metadata_custom_names (list of string): The names of tensors to store
            in custom field of metadata, the argument only used when save
            metadata is True. Defaults to [].
        """
        self._files_dir = files_dir
        self._reserved_count = reserved_count
        self._video_format = video_format
        self._thumbnail_format = thumbnail_format
        self._fps = fps
        self._image_name = image_name
        self._save_metadata = save_metadata
        self._metadata_frame_names = metadata_frame_names
        self._metadata_custom_names = metadata_custom_names
        self._metadata = None
        self._reserved_blobs = []
        self._video_recorder = None
        self._queue = None

    def _abs_file_name(self, file_name):
        """Get absolute file name for a given file name.
        """
        return os.path.join(self._files_dir['abs'], file_name)

    def _relative_file_name(self, file_name):
        """Get relative file name for a given file name.
        """
        return os.path.join(self._files_dir['relative'], file_name)

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of module execution."""
        # TODO(JiaKuan Su): Currently, I only handle the case for batch_size=1,
        # please help complete the case for batch_size>1.
        blob = blobs[0]
        image = blob.fetch(self._image_name)
        im_width = image.shape[1]
        im_height = image.shape[0]
        timestamp = float(blob.fetch('timestamp'))
        mode = int(blob.fetch('mode'))

        # Check the dimension of image tensor.
        if image.ndim != 3:
            raise RuntimeError('The input "image" tensor is not 3-dimensional.')

        # Handle alert mode.
        if mode == _MODE.ALERT_START:
            if not os.path.exists(self._files_dir['abs']):
                os.makedirs(self._files_dir['abs'])

            if self._save_metadata:
                # Construct the metadata file name.
                metadata_file = '{}.json'.format(timestamp)
                abs_metadata_name = self._abs_file_name(metadata_file)
                relative_metadata_name = self._relative_file_name(metadata_file)
                # Feed the metadata file name to blob.
                blob.feed('metadata_name', np.array(relative_metadata_name))
                # Construct the customized names and values to store in metadata.
                metadata_custom_obj = dict()
                for name in self._metadata_custom_names:
                    metadata_custom_obj[name] = blob.fetch(name).tolist()

            video_file = '{}.{}'.format(timestamp, self._video_format)
            abs_video_name = self._abs_file_name(video_file)
            relative_video_name = self._relative_file_name(video_file)
            thumbnail_file = '{}.{}'.format(timestamp, self._thumbnail_format)
            abs_thumbnail_name = self._abs_file_name(thumbnail_file)
            relative_thumbnail_name = self._relative_file_name(thumbnail_file)
            video_size = (im_width, im_height)
            self._queue = Queue()
            args = (abs_video_name,
                    abs_thumbnail_name,
                    self._fps,
                    video_size,
                    self._save_metadata,
                    abs_metadata_name if self._save_metadata else None,
                    self._metadata_frame_names,
                    metadata_custom_obj if self._save_metadata else None,
                    self._queue,)
            self._video_recorder = threading.Thread(target=_record_video,
                                                    args=args)
            self._video_recorder.setDaemon(True)
            self._video_recorder.start()

            # Record reserved images.
            for reserved_blob in self._reserved_blobs:
                self._queue.put({
                    'command': 'RECORD',
                    'blob': reserved_blob,
                    'thumbnail': False
                })
            # Record current image.
            self._queue.put({
                'command': 'RECORD',
                'blob': blob,
                'thumbnail': True
            })

            blob.feed('video_name', np.array(relative_video_name))
            blob.feed('thumbnail_name', np.array(relative_thumbnail_name))
        elif mode == _MODE.ALERTING:
            self._queue.put({
                'command': 'RECORD',
                'blob': blob,
                'thumbnail': False
            })
        elif mode == _MODE.ALERT_END:
            self._queue.put({
                'command': 'END'
            })
            self._video_recorder = None
            self._queue = None

        # Insert the newest blob to reserved buffer.
        self._reserved_blobs.append(blob)
        # Remove the oldest blob from the reserved buffer if necessary.
        if len(self._reserved_blobs) > self._reserved_count:
            self._reserved_blobs.pop(0)

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        if not self._video_recorder is None:
            logging.warn('Video recorder has not finished yet, '
                         'stop it elegantly')
            self._queue.put({
                'command': 'END'
            })
            self._video_recorder.join()


class OutputModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module to output the results."""

    def __init__(self, send_event):
        """Create a new `OutputModule`.

        Args:
          send_event (function): The callback function for sending events.
        """
        self._send_event = send_event

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of module execution."""
        for blob in blobs:
            mode = int(blob.fetch('mode'))
            timestamp = float(blob.fetch('timestamp'))
            if mode == _MODE.ALERT_START:
                video_name = str(blob.fetch('video_name'))
                thumbnail_name = str(blob.fetch('thumbnail_name'))
                triggered = blob.fetch('labels').tolist()
                event_type = 'tripwire_alert'
                content = {
                    'triggered': triggered,
                    'video_name': video_name,
                    'thumbnail_name': thumbnail_name
                }
                if blob.has('metadata_name'):
                    content['metadata_name'] = str(blob.fetch('metadata_name'))

                self._send_event(event_type, timestamp, content)

                logging.info('Sent event type: "{}", timestamp: "{}", content:'
                             ' "{}"'.format(event_type, timestamp, content))

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        pass


class DrawTripwireModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for drawing the tripwire."""

    def __init__(self, region, normal_color, alert_color):
        """Create a new `DrawTripwireModule`.

        Args:
          region (tuple): Range of the region. The tuple contains:
            xmin (int): The left position.
            ymin (int): The top position.
            xmax (int): The right position.
            ymax (int): The bottom position.
          normal_color (tuple): The tripwire color in normal mode.
            B (float): The blue channel, range in [0, 1].
            G (float): The green channel, range in [0, 1].
            R (float): The red channel, range in [0, 1].
          alert_color (tuple): The tripwire color in alert mode.
            B (float): The blue channel, range in [0, 1].
            G (float): The green channel, range in [0, 1].
            R (float): The red channel, range in [0, 1].
        """
        self._region = region
        self._normal_color = normal_color
        self._alert_color = alert_color

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of module execution."""
        # TODO(JiaKuan Su): Currently, I only handle the case for batch_size=1,
        # please help complete the case for batch_size>1.
        blob = blobs[0]
        image = blob.fetch('image')
        mode = int(blob.fetch('mode'))
        if mode == _MODE.NORMAL:
            color = self._normal_color
        else:
            color = self._alert_color
        drawn_image = self._draw_tripwire(image, color)
        blob.feed('drawn_image', drawn_image)

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        pass

    def _draw_tripwire(self, image, color, alpha=0.5):
        """Draw tripwire on an image.

        Args:
          image (numpy `ndarray`): The image to draw.
          color (tuple): The tripwire color.
            B (float): The blue channel, range in [0, 1].
            G (float): The green channel, range in [0, 1].
            R (float): The red channel, range in [0, 1].
          alpha (float): The level for alpha blending. Defaults to 0.5.
        """
        (xmin, ymin, xmax, ymax) = (self._region[0], self._region[1],
                                    self._region[2], self._region[3])
        drawn_image = image.astype(np.uint32).copy()
        for c in range(3):
            drawn_image[ymin:ymax, xmin:xmax, c] = \
                image[ymin:ymax, xmin:xmax, c] * (1 - alpha) \
                + alpha * color[c] * 255
        drawn_image = drawn_image.astype(np.uint8)
        return drawn_image

"""The modules used by tripwire worker."""

import threading
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
                 labels_to_find,
                 min_score_thresh=0.25):
        """Create a new `InRegionDetectionModule`.

        Args:
          category_index (dict): The labels category index.
          labels_to_find (list of string): The interested object labels to find.
          region (tuple): Range of the region. The tuple contains:
            xmin (int): The left position.
            ymin (int): The top position.
            xmax (int): The right position.
            ymax (int): The bottom position.
          min_score_thresh (float): The minimum threshold of score to detect.
        """
        self._category_index = category_index
        self._labels_to_find = labels_to_find
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
            in_region_labels = self._detect_in_region_objects(boxes,
                                                              scores,
                                                              classes,
                                                              num,
                                                              im_width,
                                                              im_height)
            blob.feed('in_region_labels', in_region_labels)

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
          numpy `ndarray`: The labels of objects that are in the region.
        """
        in_region_labels = []

        for i in range(num):
            # Check its label is interested or not.
            class_id = int(classes[i])
            if not class_id in self._category_index:
                continue
            label = self._category_index[class_id]
            if not label in self._labels_to_find:
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

        return np.array(in_region_labels)


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
        in_region_labels = blob.fetch('in_region_labels')

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


def _record_video(file_name, fps, video_size, queue, codec='MJPG'):
    """Threading function to record a video.

    Args:
      file_name (string): The name of recorded video.
      fps (int): The FPS of recorded video.
      video_size (tuple): The size of recorded video. The tuple contains:
        width (int): The video width.
        height (int): The video height.
      queue (`queue.Queue`): The task queue.
      coded (string): The codec of recorded video. Defaults to 'MJPG'.
    """
    logging.info('Start recording {}'.format(file_name))

    # TODO(JiaKuan Su): MJPEG is heavy, please use another codec, such as h264.
    if cv2.__version__.startswith('2.'):
        # OpenCV 2.X
        fourcc = cv2.cv.FOURCC(*codec)
    else:
        # OpenCV 3.X
        fourcc = cv2.VideoWriter_fourcc(*codec)
    video_writer = cv2.VideoWriter(file_name, fourcc, fps, video_size)

    while True:
        task = queue.get(block=True)
        command = task['command']
        if command == 'RECORD':
            video_writer.write(task['image'])
        elif command == 'END':
            break

    video_writer.release()
    logging.info('End recording {}'.format(file_name))


class VideoRecordModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module for recording video clips."""

    def __init__(self, reserved_count, fps, image_name='image'):
        """Create a new `VideoRecordModule`.

        Args:
          reserved_count (int): The number of reseved images before alert mode.
          fps (int): The FPS of recorded video.
          image_name (string): The name of input tensor to read. Defaults to
            "image".
        """
        self._reserved_count = reserved_count
        self._fps = fps
        self._image_name = image_name
        self._reserved_images = []
        self._video_recorder = None
        self._queue = None

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
        timestamp = str(blob.fetch('timestamp'))
        mode = int(blob.fetch('mode'))

        # Check the dimension of image tensor.
        if image.ndim != 3:
            raise RuntimeError('The input "image" tensor is not 3-dimensional.')

        # Insert the newest image to reserved buffer.
        self._reserved_images.append(image)
        # Remove the oldest image from the reserved buffer if necessary.
        if len(self._reserved_images) > self._reserved_count:
            self._reserved_images.pop(0)

        # Handle alert mode.
        if mode == _MODE.ALERT_START:
            # TODO(JiaKuan Su): Browser can't play avi files, use mp4 instead.
            file_name = '{}.avi'.format(timestamp)
            video_size = (im_width, im_height)
            self._queue = Queue()
            args = (file_name, self._fps, video_size, self._queue,)
            self._video_recorder = threading.Thread(target=_record_video,
                                                    args=args)
            self._video_recorder.setDaemon(True)
            self._video_recorder.start()
            for reserved_image in self._reserved_images:
                self._queue.put({
                    'command': 'RECORD',
                    'image': reserved_image
                })
        elif mode == _MODE.ALERTING:
            self._queue.put({
                'command': 'RECORD',
                'image': image
            })
        elif mode == _MODE.ALERT_END:
            self._queue.put({
                'command': 'END'
            })
            self._video_recorder = None
            self._queue = None

        return blobs

    def destroy(self):
        """The routine of module destruction."""
        if not self._video_recorder is None:
            logging.warn('Video recorder has not finished yet, '
                         'stop it elegantly')
            self._queue.put({
                'command': 'END'
            })


class OutputModule(IModule):
    # TODO(JiaKuan Su): Please fill the detailed docstring.
    """The module to output the results."""

    def prepare(self):
        """The routine of module preparation."""
        pass

    def execute(self, blobs):
        # TODO(JiaKuan Su): Please fill the detailed docstring.
        """The routine of module execution."""
        for blob in blobs:
            in_region_labels = blob.fetch('in_region_labels')
            if in_region_labels.shape[0] > 0:
                # TODO(JiaKuan Su): Send back to brain, not just logging.
                logging.info('Detect {} in region.'.format(in_region_labels))

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

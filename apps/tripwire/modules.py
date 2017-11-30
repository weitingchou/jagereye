"""The modules used by tripwire worker."""

import numpy as np
import tensorflow as tf

from jagereye.streaming import IModule
from jagereye.util import logging


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
            # Expand dimensions since the model expects images to have shape:
            # [1, None, None, 3]
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
        for blob in blobs:
            image = blob.fetch('image')
            in_region_labels = blob.fetch('in_region_labels')
            if in_region_labels.shape[0] > 0:
                color = self._alert_color
            else:
                color = self._normal_color
            drawn_image = image.astype(np.uint32).copy()
            drawn_image = self._draw_tripwire(drawn_image, color)
            drawn_image = drawn_image.astype(np.uint8)
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
        for c in range(3):
            image[ymin:ymax, xmin:xmax, c] = \
                image[ymin:ymax, xmin:xmax, c] * (1 - alpha) \
                + alpha * color[c] * 255
        return image

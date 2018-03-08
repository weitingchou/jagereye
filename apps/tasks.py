import ray
import cv2
import numpy as np

from jagereye.util import logging


def detect_motion(frames, sensitivity=80):
    """Detect motion between frames.

    Args:
        frames: A list of frame objects, each a object of format
            {"image": IMAGE_BINARY, "timestamp": TIMESTAMP}.
        sensitivity: The sensitivity of motion detection, range from 1
                     to 100. Defaults to 80.
    Returns:
        A list of frame object IDs that have motions being detected among them.
    """
    sensitivity_clamp = max(1, min(sensitivity, 100))
    threshold = (100 - sensitivity_clamp) * 0.05
    num_frames = len(frames)
    if num_frames < 1:
        return []
    elif num_frames == 1:
        return frames

    results = [0]
    last = cv2.cvtColor(frames[0]["image"], cv2.COLOR_BGR2GRAY)
    for i in range(1, num_frames):
        current = cv2.cvtColor(frames[i]["image"], cv2.COLOR_BGR2GRAY)
        res = cv2.absdiff(last, current)
        # Remove the noise and do the threshold.
        res = cv2.blur(res, (5, 5))
        res = cv2.morphologyEx(res, cv2.MORPH_OPEN, None)
        res = cv2.morphologyEx(res, cv2.MORPH_CLOSE, None)
        ret, res = cv2.threshold(res, 10, 255, cv2.THRESH_BINARY_INV) #pylint: disable=unused-variable
        # Count the number of black pixels.
        num_black = np.count_nonzero(res == 0)
        # Calculate the image size.
        im_size = current.shape[1] * current.shape[0]
        # Calculate the average of black pixel in the image.
        avg_black = (num_black * 100.0) / im_size
        # Detect moving by testing whether the average of black exceeds the
        # threshold or not.
        if avg_black >= threshold:
            results.append(i)
        last = current
    return results


def detect_in_region(height,
                     width,
                     detections,
                     category_index,
                     region,
                     triggers,
                     threshold=0.25):
    """Detect if object is in the alerted region.

    Args:
        height: The height of the input images.
        width: The width of the input images.
        detections: A list of object detection result objects, each a object of
                    format (bboxes, scores, classes, num_detctions).
        category_index: A dict() of mapping between object detection indexes
                        and classes.
        region: A tuple of
        triggers:
        threshold:

    Returns:
        A list of tuple list that specifies the triggered detections, each a
        tuple list of format [(label, detect_index), ...].
    """
    r_xmin, r_ymin, r_xmax, r_ymax = region
    results = []
    for i in range(len(detections)):
        (bboxes, scores, classes, num_detections) = detections[i]

        # TODO: We need to
        in_region_labels = []
        for j in range(int(num_detections[0])):
            # Check if score passes the threshold.
            if scores[0][j] < threshold:
                continue
            # print("scores: {}, threshold: {}".format(scores[0][j], threshold))
            # Check if the object in in the trigger list.
            # XXX: Is it posssible to generate index that is not in the
            #      category_index list?
            try:
                label = category_index[int(classes[0][j])]
                # print("label: {}".format(label))
                if label not in triggers:
                    continue
            except KeyError:
                continue
            # Check whether the object is in region or not.
            o_ymin, o_xmin, o_ymax, o_xmax = bboxes[0][j]
            o_xmin, o_ymin, o_xmax, o_ymax = (o_xmin * width, o_ymin * height,
                                              o_xmax * width, o_ymax * height)
            overlap_region = max(0.0, min(o_xmax, r_xmax) - max(o_xmin, r_xmin)) \
                * max(0.0, min(o_ymax, r_ymax) - max(o_ymin, r_ymin))
            if overlap_region > 0.0:
                # print("overlap_region: {}".format(overlap_region))
                in_region_labels.append((label, j))
        results.append(in_region_labels)
    return results


def draw_tripwire(frame, region, color, alpha=0.5):
    (xmin, ymin, xmax, ymax) = region
    src_image = frame["image"]
    drawn_image = src_image.astype(np.uint32).copy()
    for c in range(3):
        drawn_image[ymin:ymax, xmin:xmax, c] = \
            src_image[ymin:ymax, xmin:xmax, c] * (1 - alpha) \
            + alpha * color[c] * 255
    return drawn_image.astype(np.uint8)

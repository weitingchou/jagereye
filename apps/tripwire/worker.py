"""The tripwire worker."""

import os

from jagereye.streaming import VideoStreamCapturer
from jagereye.streaming import DisplayModule
from jagereye.streaming import Pipeline

from modules import DrawTripwireModule
from modules import InRegionDetectionModule
from modules import ObjectDetectionModule
from modules import OutputModule


MODEL_NAME = 'ssd_mobilenet_v1_coco_11_06_2017'
LABELS_PATH = 'coco.labels'
LABELS_TO_FIND = ['person']
VISUALIZE = True
NORMAL_COLOR = (226, 137, 59)
ALERT_COLOR = (66, 194, 244)


def create_category_index(labels_path):
    """Create the index of label categories"""
    with open(labels_path) as f:
        lines = f.readlines()
    category_index = dict()
    for line in lines:
        # Format: "id label"
        splits = line.strip().split(' ')
        category_index[int(splits[0])] = splits[1]
    return category_index


def get_ckpt_path(model_name):
    """Get check point file path from given model name."""
    ckpt_path = os.path.join('models', model_name, 'frozen_inference_graph.pb')
    return ckpt_path


def normalize_color(color):
    """Normalize color from [0, 255] to [0, 1]."""
    norms = []
    for i in range(3):
        norms.append(color[i] / 255.0)
    return (norms[0], norms[1], norms[2])


def main(task_info):
    category_index = create_category_index(LABELS_PATH)
    ckpt_path = get_ckpt_path(MODEL_NAME)
    normal_color = normalize_color(NORMAL_COLOR)
    alert_color = normalize_color(ALERT_COLOR)
    src = task_info['src']
    region = task_info['region']

    pipeline = Pipeline(cap_interval=100)

    pipeline.source(VideoStreamCapturer(src)) \
            .pipe(ObjectDetectionModule(ckpt_path)) \
            .pipe(InRegionDetectionModule(category_index,
                                          region,
                                          LABELS_TO_FIND)) \
            .pipe(OutputModule())

    if VISUALIZE:
        pipeline.pipe(DrawTripwireModule(region, normal_color, alert_color)) \
                .pipe(DisplayModule(image_name='drawn_image'))

    pipeline.start()
    pipeline.await_termination()


if __name__ == '__main__':
    main({
        'src': 'rtsp://192.168.0.3/stream1',
        'region': (100, 100, 400, 400)
    })

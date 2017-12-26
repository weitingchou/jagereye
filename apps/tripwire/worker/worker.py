"""The tripwire worker."""

import argparse
import os
import sys

from jagereye.util import logging
from jagereye.streaming import VideoStreamCapturer
from jagereye.streaming import DisplayModule
from jagereye.streaming import Pipeline
from jagereye.worker import Worker

from modules import DrawTripwireModule
from modules import InRegionDetectionModule
from modules import MotionDetectionModule
from modules import ObjectDetectionModule
from modules import OutputModule
from modules import TripwireModeModule
from modules import VideoRecordModule


MODEL_NAME = 'ssd_mobilenet_v1_coco_11_06_2017'
LABELS_PATH = 'coco.labels'
FPS = 15
RESERVED_SECONDS = 3
VISUALIZE = False
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


def worker_fn(context):
    """The main worker function"""
    send_event = context['send_event']
    config = context['config']

    cap_interval = 1000.0 / FPS
    reserved_count = FPS * RESERVED_SECONDS
    category_index = create_category_index(LABELS_PATH)
    ckpt_path = get_ckpt_path(MODEL_NAME)
    normal_color = normalize_color(NORMAL_COLOR)
    alert_color = normalize_color(ALERT_COLOR)
    src = config['src']
    region = config['region']
    triggers = config['triggers']

    pipeline = Pipeline(cap_interval=cap_interval)

    pipeline.source(VideoStreamCapturer(src)) \
            .pipe(MotionDetectionModule()) \
            .pipe(ObjectDetectionModule(ckpt_path)) \
            .pipe(InRegionDetectionModule(category_index,
                                          region,
                                          triggers)) \
            .pipe(TripwireModeModule(reserved_count=reserved_count)) \
            .pipe(DrawTripwireModule(region, normal_color, alert_color)) \
            .pipe(VideoRecordModule(reserved_count,
                                    FPS,
                                    image_name='drawn_image')) \
            .pipe(OutputModule(send_event))

    if VISUALIZE:
        pipeline.pipe(DisplayModule(image_name='drawn_image'))

    pipeline.start()
    pipeline.await_termination()


def _send_event(name, context):
    """Mock event for sending event in standalone mode.

    Args:
      event (string)
    """
    logging.info('From Mocked send_event with event name: "{}", context: "{}"'
                 .format(name, context))


def main(worker_id, standalone = False, config=None):
    if not standalone:
        worker = Worker(worker_id)
        worker.register_pipeline(worker_fn)
        worker.start()
    else:
        context = {
            'send_event': _send_event,
            'config': config
        }
        worker_fn(context)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Add required arguments.
    parser.add_argument('id',
                        help='worker ID in normal mode',
                        type=str)
    # Add arguments for standalone mode.
    sl_group = parser.add_argument_group('standalone mode')
    sl_group.add_argument('--standalone',
                          help='run in standalone mode',
                          action='store_true')
    sl_group.add_argument('-s',
                          '--src',
                          help='streaming source in standalone mode',
                          type=str)
    sl_group.add_argument('-r',
                          '--region',
                          help='region in standalone mode',
                          type=str)
    sl_group.add_argument('-t',
                          '--triggers',
                          help='triggers in standalone mode',
                          type=str)

    args = parser.parse_args()

    if not args.standalone:
        config = None
    else:
        # Handle arguments for standalone mode.
        # Check the required arguments for standalone mode.
        if args.src is None or args.region is None or args.triggers is None:
            parser.error('standalone mode requires --src, --region and'
                         ' --triggers')
        # Parse the region.
        p_list = args.region.split(',')
        p_list = list(map(int, p_list))
        if len(p_list) != 4:
            parser.error('Format for --region: xmin,ymin,xmax,ymax')
        region = tuple(p_list)
        # Parse the triggers.
        triggers = args.triggers.split(',')
        # Construct the config for standalone mode.
        config = {
            'src': args.src,
            'region': region,
            'triggers': triggers
        }

    main(args.id, standalone=args.standalone, config=config)

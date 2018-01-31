"""The tripwire worker."""

import argparse
import os
import sys

from jagereye.util import logging
from jagereye.streaming import ImageSaveModule
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


WORKER_NAME = 'tripwire'
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


def worker_fn(params, files_dir, send_event):
    """The main worker function"""
    config = params['pipelines'][0]['params']

    cap_interval = 1000.0 / FPS
    reserved_count = FPS * RESERVED_SECONDS
    category_index = create_category_index(LABELS_PATH)
    ckpt_path = get_ckpt_path(MODEL_NAME)
    normal_color = normalize_color(NORMAL_COLOR)
    alert_color = normalize_color(ALERT_COLOR)
    src = params['source']['url']
    region = config['region']
    region_tuple = (
        region[0]['x'],
        region[0]['y'],
        region[1]['x'],
        region[1]['y']
    )
    triggers = config['triggers']
    metadata_frame_names = ['mode', 'labels', 'boxes', 'scores']
    metadata_custom_names = ['region']

    pipeline = Pipeline(cap_interval=cap_interval)

    pipeline.source(VideoStreamCapturer(src)) \
            .pipe(MotionDetectionModule()) \
            .pipe(ObjectDetectionModule(ckpt_path)) \
            .pipe(InRegionDetectionModule(category_index,
                                          region_tuple,
                                          triggers)) \
            .pipe(TripwireModeModule(reserved_count=reserved_count)) \
            .pipe(DrawTripwireModule(region_tuple,
                                     normal_color,
                                     alert_color,
                                     always_draw=VISUALIZE)) \
            .pipe(ImageSaveModule(files_dir,
                                  max_width=300,
                                  image_name='drawn_image')) \
            .pipe(VideoRecordModule(files_dir,
                                    reserved_count,
                                    FPS,
                                    save_metadata=True,
                                    metadata_frame_names=metadata_frame_names,
                                    metadata_custom_names=metadata_custom_names)) \
            .pipe(OutputModule(send_event))

    if VISUALIZE:
        pipeline.pipe(DisplayModule(image_name='drawn_image'))

    pipeline.start()
    pipeline.await_termination()


def _send_event(event_type, timestamp, content):
    """Mock function for sending event in standalone mode.

    Args:
      event_type (string): The event type.
      timestamp (float): The timestamp of the event.
      content (dict): The event content.
    """
    logging.info('From Mocked send_event with event type: "{}", timestamp: "{}"'
                 ', content: "{}"'.format(event_type, timestamp, content))


def main(worker_id, standalone = False, params=None):
    if not standalone:
        worker = Worker(WORKER_NAME, worker_id)
        worker.register_pipeline(worker_fn)
        worker.start()
    else:
        relative_files_dir = os.path.join(WORKER_NAME, worker_id)
        abs_files_dir = os.path.join('~/jagereye_shared', relative_files_dir)
        abs_files_dir = os.path.expanduser(abs_files_dir)
        files_dir = {
            'abs': abs_files_dir,
            'relative': relative_files_dir
        }
        worker_fn(params, files_dir, _send_event)


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
        params = None
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
        region = [{
            'x': p_list[0],
            'y': p_list[1]
        }, {
            'x': p_list[2],
            'y': p_list[3]
        }]
        # Parse the triggers.
        triggers = args.triggers.split(',')
        # Construct the parameters for standalone mode.
        params = {
            'source': {
                'url': args.src
            },
            'pipelines': [{
                'params': {
                    'region': region,
                    'triggers': triggers
                }
            }]
        }

    main(args.id, standalone=args.standalone, params=params)

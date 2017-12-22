FROM jagereye/worker

MAINTAINER JiaKuan Su <feabries@gmail.com>

ENV HOME /root
ENV WORKER_DIR apps/tripwire/worker
ENV MODEL_NAME ssd_mobilenet_v1_coco_11_06_2017

# Download TensorFlow model files.
WORKDIR models
RUN wget http://download.tensorflow.org/models/object_detection/$MODEL_NAME.tar.gz
RUN tar zxvf $MODEL_NAME.tar.gz
RUN rm $MODEL_NAME.tar.gz
RUN find . ! -name 'frozen_inference_graph.pb' -type f -exec rm -r {} +
WORKDIR $HOME

# Copy files about tripwire worker.
# TODO(JiaKuan Su): Use .pyc only.
COPY $WORKER_DIR/worker.py .
COPY $WORKER_DIR/modules.py .
COPY $WORKER_DIR/coco.labels .

CMD python3 worker.py ${worker_id}

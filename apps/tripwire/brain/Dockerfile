FROM jagereye/brain

MAINTAINER JiaKuan Su <feabries@gmail.com>

ENV HOME /root
ENV APP_DIR ${HOME}/jagereye/apps/tripwire/brain

WORKDIR ${HOME}

# Create project strcture
RUN mkdir -p ${APP_DIR}

# Copy application files.
# TODO(JiaKuan Su): Use .pyc only.
COPY brain.py ${APP_DIR}

WORKDIR ${APP_DIR}

ENTRYPOINT ["python3"]
CMD ["brain.py"]

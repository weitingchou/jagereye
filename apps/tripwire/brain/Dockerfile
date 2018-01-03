FROM jagereye/brain

MAINTAINER JiaKuan Su <feabries@gmail.com>

ENV HOME /root
ENV FILES_DIR apps/tripwire/brain

WORKDIR ${HOME}

# Copy files about tripwire brain.
# TODO(JiaKuan Su): Use .pyc only.
COPY ${FILES_DIR}/brain.py .

CMD python3 brain.py

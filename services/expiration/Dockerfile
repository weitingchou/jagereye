FROM ubuntu:16.04

MAINTAINER JiaKuan Su <feabries@gmail.com>

ENV HOME /root
ENV NODE_VERSION 8.9.3

WORKDIR ${HOME}

# Install system packages.
RUN apt-get update && apt-get install -y --no-install-recommends \
        apt-transport-https \
        ca-certificates \
        curl \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js via nvm
RUN curl -o- https://raw.githubusercontent.com/creationix/nvm/v0.33.8/install.sh | bash
RUN . .nvm/nvm.sh && \
    nvm install ${NODE_VERSION} && \
    nvm alias default ${NODE_VERSION} && \
    nvm use default && \
    rm -r .nvm/.cache
ENV PATH ${HOME}/.nvm/versions/node/v${NODE_VERSION}/bin:${PATH}

# Install Yarn
RUN curl -sS https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add -
RUN echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list
RUN apt-get update && apt-get install -y --no-install-recommends \
        yarn \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create services structure
RUN mkdir -p jagereye/services/expiration
RUN mkdir -p jagereye/shared

# Copy service files
COPY . ./jagereye/services/expiration

# Copy shared files
# [NOTE] Shared files should be copied in to the build context before
#        running docker build
COPY event.json ./jagereye/shared
COPY config.yml ./jagereye/shared

WORKDIR ${HOME}/jagereye/services/expiration

# Install Expiration Service
RUN yarn install && \
    yarn cache clean

CMD yarn start

FROM cameronx/aws-deployer:latest

RUN set -eux \
    && apt-get update && apt-get install -y --no-install-recommends \
      apt-transport-https \
      ca-certificates \
      curl \
      gnupg \
      jq \
      less \
      lsb-release \
      make \
      vim \
      zip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ARG AWS_CDK_VERSION=2.69.0
RUN npm install -g aws-cdk@${AWS_CDK_VERSION}

COPY requirements.txt /tmp/build/requirements.txt
RUN pip install -r /tmp/build/requirements.txt \
    && rm -rf /tmp/build

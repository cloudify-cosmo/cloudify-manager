FROM python:3.10-slim

ENV WORKER_COUNT=1
ENV MAX_WORKER_COUNT=4
ENV MAX_REQUESTS=1000
ENV PORT=8100
ENV SECRET_KEY=abcdefgh-secret-1234
ENV HASH_SALT=abcdefgh-salt-1234
ENV POSTGRES_DB=cloudify_db
ENV POSTGRES_HOST=postgresql
ENV POSTGRES_USER=cloudify
ENV POSTGRES_PASSWORD=cloudify
# FILE_SERVER_TYPE=minio or local
ENV FILE_SERVER_TYPE=s3
ENV CONFIG_FILE_PATH=/opt/rest-service/docker/config.yaml

RUN --mount=type=cache,target=/root/.cache \
    apt-get update \
    && \
    apt-get install -y \
      libpq-dev \
      gcc \
      libffi-dev \
      libsasl2-dev \
      libldap2-dev \
      libkrb5-dev \
      git

RUN mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

WORKDIR /opt

COPY . rest-service

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      -r rest-service/requirements.txt \
      rest-service/ \
      gunicorn

RUN --mount=type=ssh \
    pip install \
    -r rest-service/requirements_ssh.txt

RUN mkdir /src
COPY docker/cloudify.pth /usr/local/lib/python3.10/site-packages/cloudify.pth

RUN mkdir -p \
      /var/log/cloudify/rest \
      /opt/manager \
      /run/cloudify-restservice

ADD https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/master/cfy_manager/components/restservice/config/license_key.pem.pub /opt/manager/license_key.pem.pub

ENTRYPOINT /opt/rest-service/docker/entrypoint.sh

FROM python:3.11-slim

ENV WORKER_COUNT=4
ENV MAX_WORKER_COUNT=4
ENV MAX_REQUESTS=1000
ENV PORT=8100
ENV SECRET_KEY=abcdefgh-secret-1234
ENV HASH_SALT=abcdefgh-salt-1234
ENV POSTGRES_DB=cloudify_db
ENV POSTGRES_HOST=postgresql
ENV POSTGRES_USER=cloudify
ENV POSTGRES_PASSWORD=cloudify
# FILE_SERVER_TYPE=s3 or local
ENV FILE_SERVER_TYPE=s3

ARG PREMIUM=true

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

COPY requirements.txt requirements.txt
COPY requirements_ssh.txt requirements_ssh.txt

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      gunicorn \
      alembic \
      -r requirements.txt

RUN --mount=type=ssh \
    if [ -n "${PREMIUM}" ]; then pip install -r requirements_ssh.txt; fi

RUN mkdir /src
COPY docker/cloudify.pth /usr/local/lib/python3.11/site-packages/cloudify.pth

RUN mkdir -p \
      /var/log/cloudify/rest \
      /opt/manager \
      /run/cloudify-restservice

ADD https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/master/cfy_manager/components/restservice/config/license_key.pem.pub /opt/manager/license_key.pem.pub

COPY . rest-service

RUN --mount=type=cache,target=/root/.cache \
    pip install rest-service/

ENTRYPOINT /opt/rest-service/docker/entrypoint.sh

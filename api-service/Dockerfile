FROM python:3.11-slim

ARG username=cfyuser
ARG groupname=cfyuser

ENV WORKER_COUNT=4
ENV MAX_REQUESTS=1000
ENV PORT=8101
ENV POSTGRES_DB=cloudify_db
ENV POSTGRES_HOST=postgresql
ENV POSTGRES_USER=cloudify
ENV POSTGRES_PASSWORD=cloudify

RUN --mount=type=cache,target=/root/.cache \
    apt-get update \
    && \
    apt-get install -y \
      gcc \
      libffi-dev \
      libpq-dev

WORKDIR /opt

COPY requirements.txt requirements.txt

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      gunicorn \
      -r requirements.txt

COPY docker/cloudify.pth /usr/local/lib/python3.11/site-packages/cloudify.pth

RUN mkdir -p \
    /opt/manager \
    /run/cloudify-api \
    /var/log/cloudify/rest

COPY . api-service

RUN --mount=type=cache,target=/root/.cache \
    pip install api-service/

RUN groupadd $groupname && useradd -u 1000 -g $groupname $username

RUN chown -R $username:$groupname \
    /opt \
    /run/cloudify-api \
    /var/log/cloudify

USER 1000

ENTRYPOINT /opt/api-service/docker/entrypoint.sh

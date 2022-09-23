FROM python:3.10-slim

ENV WORKER_COUNT=1
ENV MAX_WORKER_COUNT=4
ENV MAX_REQUESTS=1000
ENV PORT=8100
ENV SECRET_KEY=abcdefgh-secret-1234
ENV POSTGRES_DB=cloudify_db
ENV POSTGRES_HOST=postgresql
ENV POSTGRES_USER=cloudify
ENV POSTGRES_PASSWORD=cloudify

RUN --mount=type=cache,target=/root/.cache \
    apt-get update \
    && \
    apt-get install -y \
      libpq-dev \
      gcc \
      libffi-dev

WORKDIR /opt

COPY . rest-service

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      -r rest-service/requirements.txt \
      rest-service/ \
      gunicorn

RUN mkdir /src
COPY docker/cloudify.pth /usr/local/lib/python3.10/site-packages/cloudify.pth

RUN mkdir -p \
      /var/log/cloudify/rest \
      /opt/manager \
      /run/cloudify-restservice

ENTRYPOINT /opt/rest-service/docker/entrypoint.sh

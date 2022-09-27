FROM python:3.10-slim

# For rest-service
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
      libffi-dev \
      gcc

WORKDIR /opt

COPY . execution-scheduler

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      -r execution-scheduler/requirements.txt \
      execution-scheduler/

RUN mkdir /src
COPY docker/cloudify.pth /usr/local/lib/python3.10/site-packages/cloudify.pth

RUN mkdir -p \
    /opt/manager \
    /var/log/cloudify/execution-scheduler

ENTRYPOINT /opt/execution-scheduler/docker/entrypoint.sh

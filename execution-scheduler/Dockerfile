FROM python:3.11-slim

ARG username=cfyuser
ARG groupname=cfyuser

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

COPY requirements.txt requirements.txt

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      -r requirements.txt

RUN mkdir -p \
    /opt/manager \
    /var/log/cloudify/execution-scheduler \
    /src

COPY docker/cloudify.pth /usr/local/lib/python3.11/site-packages/cloudify.pth

COPY . execution-scheduler

RUN --mount=type=cache,target=/root/.cache \
    pip install execution-scheduler/

RUN groupadd $groupname && useradd -u 1000 -g $groupname $username

RUN chown -R $username:$groupname \
    /opt \
    /src \
    /var/log/cloudify

USER 1000

ENTRYPOINT /opt/execution-scheduler/docker/entrypoint.sh

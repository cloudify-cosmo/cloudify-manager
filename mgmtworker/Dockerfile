FROM python:3.11-slim

ARG username=cfyuser
ARG groupname=cfyuser

ENV REST_HOST=nginx
ENV REST_PORT=53333
ENV LOCAL_REST_CERT_FILE=/etc/cloudify/ssl/cloudify_internal_ca_cert.pem
ENV AGENT_WORK_DIR=/opt/mgmtworker
ENV MANAGER_NAME=cloudify-manager

RUN --mount=type=cache,target=/root/.cache \
    apt-get update \
    && \
    apt-get install -y \
      libpq-dev \
      gcc \
      git \
      libkrb5-dev \
      libffi-dev

WORKDIR /opt

COPY requirements.txt requirements.txt

RUN --mount=type=cache,target=/root/.cache \
    pip install \
      --upgrade pip \
      -r requirements.txt

ADD https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/master\
/resources/rest-service/cloudify/types/types.yaml \
/opt/manager/resources/cloudify/types/
ADD https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/master\
/resources/rest-service/cloudify/types/types_1_3.yaml \
/opt/manager/resources/cloudify/types/
ADD https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager/master\
/resources/rest-service/cloudify/types/types_1_4.yaml \
/opt/manager/resources/cloudify/types/

COPY . mgmtworker

RUN --mount=type=cache,target=/root/.cache \
    pip install mgmtworker/

RUN groupadd $groupname && useradd -u 1000 -g $groupname $username

RUN chown -R $username:$groupname \
    /opt

USER 1000

ENTRYPOINT /opt/mgmtworker/docker/entrypoint.sh

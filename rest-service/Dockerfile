FROM python:3.10-slim

ENV WORKER_COUNT=1
ENV MAX_WORKER_COUNT=4
ENV MAX_REQUESTS=1000
ENV PORT=8101
ENV SECRET_KEY=abcdefgh-secret-1234
ENV POSTGRES_DB=cloudify_db
ENV POSTGRES_HOST=postgresql
ENV POSTGRES_USER=cloudify
ENV POSTGRES_PASSWORD=cloudify

RUN --mount=type=cache,target=/root/.cache apt-get update

RUN --mount=type=cache,target=/root/.cache apt-get install -y libpq-dev # Required for psycopg2
RUN --mount=type=cache,target=/root/.cache apt-get install -y gcc # Required for psycopg2
RUN --mount=type=cache,target=/root/.cache apt-get install -y libffi-dev # Required for cffi

WORKDIR /opt

COPY . rest-service

RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip
RUN --mount=type=cache,target=/root/.cache pip install -r rest-service/requirements.txt
RUN --mount=type=cache,target=/root/.cache pip install rest-service/
RUN --mount=type=cache,target=/root/.cache pip install gunicorn

RUN mkdir /src
COPY docker/cloudify.pth /usr/local/lib/python3.10/site-packages/cloudify.pth

RUN mkdir -p /var/log/cloudify/rest
RUN mkdir -p /opt/manager
RUN mkdir -p /run/cloudify-restservice

ENTRYPOINT /opt/rest-service/docker/entrypoint.sh

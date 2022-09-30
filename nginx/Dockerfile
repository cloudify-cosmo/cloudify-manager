FROM nginx

ENV WORKER_PROCESS=auto
ENV WORKER_CONNECTIONS=4096
ENV REST_SERVICE_PORT=8100

WORKDIR /opt

COPY . nginx

RUN mkdir -p /var/log/cloudify/nginx

RUN rm -rf /etc/nginx/conf.d/default.conf

ENTRYPOINT nginx/docker/entrypoint.sh

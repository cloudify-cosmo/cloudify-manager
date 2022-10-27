FROM nginx

ENV WORKER_PROCESS=auto
ENV WORKER_CONNECTIONS=4096
ENV REST_SERVICE_PORT=8100
ENV FILESERVER_PORT=9000

WORKDIR /opt

RUN rm -rf /etc/nginx/conf.d/default.conf

RUN mkdir -p /var/log/cloudify/nginx

COPY ./config/nginx.conf /etc/nginx/nginx.conf
COPY ./config/conf.d /etc/nginx/conf.d
COPY ./config/templates /etc/nginx/templates

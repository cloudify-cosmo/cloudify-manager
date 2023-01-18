FROM nginx

ENV WORKER_PROCESS=auto
ENV WORKER_CONNECTIONS=4096

ENV REST_SERVICE_HOST=rest-service
ENV REST_SERVICE_SERVICE_PORT=8100

ENV FILESERVER_HOST=fileserver
ENV FILESERVER_SERVICE_PORT=9000

ENV STAGE_FRONTEND_HOST=stage-frontend
ENV STAGE_FRONTNED_SERVICE_PORT=8188

ENV STAGE_BACKEND_HOST=stage-backend
ENV STAGE_BACKEND_SERVICE_PORT=8088

ENV COMPOSER_FRONTEND_HOST=composer-frontend
ENV COMPOSER_FRONTEND_SERVICE_PORT=8188

ENV COMPOSER_BACKEND_HOST=composer-backend
ENV COMPOSER_BACKEND_SERVICE_PORT=3000

WORKDIR /opt

RUN rm -rf /etc/nginx/conf.d/default.conf

RUN mkdir -p /var/log/cloudify/nginx

COPY ./config/nginx.conf /etc/nginx/nginx.conf
COPY ./config/conf.d /etc/nginx/conf.d
COPY ./config/templates /etc/nginx/templates

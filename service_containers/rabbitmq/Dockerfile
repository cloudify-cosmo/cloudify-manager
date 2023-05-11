FROM rabbitmq

ENV RABBITMQ_USERNAME=cloudify
ENV RABBITMQ_PASSWORD=c10udify
ENV RABBITMQ_NODENAME=rabbit@localhost
ENV RABBITMQ_LOG_BASE="/var/log/cloudify/rabbitmq"
ENV RABBITMQ_CONFIG_FILE="/etc/cloudify/rabbitmq/rabbitmq.config"
ENV RABBITMQ_ENABLED_PLUGINS_FILE="/etc/cloudify/rabbitmq/enabled_plugins"

RUN --mount=type=cache,target=/root/.cache \
    apt-get update \
    && \
    apt-get install -y \
      python3

COPY ./config /etc/cloudify/rabbitmq
COPY ./script /opt/rabbitmq/script
COPY ./docker /opt/rabbitmq/docker

RUN mkdir -p /var/log/cloudify/rabbitmq
RUN chmod 777 -R /var/log/cloudify/rabbitmq

RUN groupadd k8s && useradd -u 1000 -g k8s k8s

RUN chown -R k8s:k8s \
    /opt \
    /etc/cloudify \
    /var/log/cloudify

USER 1000

ENTRYPOINT ["/opt/rabbitmq/docker/entrypoint.sh"]
CMD ["rabbitmq-server"]

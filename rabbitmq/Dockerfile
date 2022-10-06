FROM rabbitmq

ENV RABBITMQ_NODENAME=rabbit@localhost
ENV RABBITMQ_LOG_BASE="/var/log/cloudify/rabbitmq"
ENV RABBITMQ_CONFIG_FILE="/etc/cloudify/rabbitmq/rabbitmq"
ENV RABBITMQ_ENABLED_PLUGINS_FILE="/etc/cloudify/rabbitmq/enabled_plugins"

RUN mkdir -p /var/log/cloudify/rabbitmq
RUN chmod 777 -R /var/log/cloudify/rabbitmq

#!/usr/bin/env -S bash -eux

/opt/rest-service/docker/prepare_secrets.sh

CONFIG_FILE="${CONFIG_FILE_PATH:-/tmp/config.yaml}"

if [ ! -e "${CONFIG_FILE}" ]; then
    echo "
manager:
    hostname: cloudify-manager
    private_ip: ${ENTRYPOINT}
" > "${CONFIG_FILE}"
fi

python -m manager_rest.configure_manager --db-wait postgresql
python -m manager_rest.configure_manager --rabbitmq-wait rabbitmq
exec python -m manager_rest.configure_manager \
    -c /tmp/config.yaml \
    --create-admin-token /mgmtworker/admin_token

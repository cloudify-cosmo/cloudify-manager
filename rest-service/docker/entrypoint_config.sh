#!/usr/bin/env -S bash -eux

/opt/rest-service/docker/prepare_secrets.sh

if [ ! -e "/tmp/config.yaml" ]; then
    echo "
manager:
    hostname: cloudify-manager
    private_ip: ${ENTRYPOINT}
" > /tmp/config.yaml
fi

python -m manager_rest.configure_manager --db-wait postgresql
python -m manager_rest.configure_manager --rabbitmq-wait rabbitmq
exec python -m manager_rest.configure_manager \
    -c /tmp/config.yaml \
    --create-admin-token /mgmtworker/admin_token

#!/usr/bin/env -S bash -eux

/opt/rest-service/docker/prepare_secrets.sh

python -m manager_rest.configure_manager --db-wait postgresql
python -m manager_rest.configure_manager --rabbitmq-wait rabbitmq

exec python -m manager_rest.configure_manager --create-admin-token /mgmtworker/admin_token


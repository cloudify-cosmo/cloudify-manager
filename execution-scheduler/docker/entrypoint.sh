#!/usr/bin/env -S bash -eux

echo "
postgresql_db_name: ${POSTGRES_DB}
postgresql_host: ${POSTGRES_HOST}
postgresql_username: ${POSTGRES_USER}
postgresql_password: ${POSTGRES_PASSWORD}
" > /opt/manager/cloudify-rest.conf

echo "
secret_key: ${SECRET_KEY}
" > /opt/manager/rest-security.conf


python -m manager_rest.configure_manager --db-wait postgresql
python -m manager_rest.configure_manager --rabbitmq-wait rabbitmq

exec cloudify-execution-scheduler

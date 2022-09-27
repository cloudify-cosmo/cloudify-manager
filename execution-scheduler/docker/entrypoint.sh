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

exec cloudify-execution-scheduler

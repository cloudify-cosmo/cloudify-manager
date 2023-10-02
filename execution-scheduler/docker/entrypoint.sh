#!/usr/bin/env -S bash -eux

set +x
echo "
postgresql_db_name: ${POSTGRES_DB}
postgresql_host: ${POSTGRES_HOST}
postgresql_username: ${POSTGRES_USER}
postgresql_password: ${POSTGRES_PASSWORD}
" > /opt/manager/cloudify-rest.conf

if [ ! -e "/opt/manager/rest-security.conf" ]; then
    echo "
{
    \"secret_key\": \"${SECRET_KEY}\",
    \"hash_salt\": \"${HASH_SALT}\"
}
" > /opt/manager/rest-security.conf
fi
set -x

python -m manager_rest.configure_manager --db-wait postgresql
python -m manager_rest.configure_manager --rabbitmq-wait rabbitmq

exec cloudify-execution-scheduler

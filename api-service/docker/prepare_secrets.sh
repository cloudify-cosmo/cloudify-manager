#!/usr/bin/env -S bash -eux

echo "Provisioning config files..."

set +x
if [ ! -e "/opt/manager/cloudify-rest.conf" ]; then
    echo "
postgresql_db_name: ${POSTGRES_DB}
postgresql_host: ${POSTGRES_HOST}
postgresql_username: ${POSTGRES_USER}
postgresql_password: ${POSTGRES_PASSWORD}
" > /opt/manager/cloudify-rest.conf
fi
set -x

echo "Config files provisioned!"

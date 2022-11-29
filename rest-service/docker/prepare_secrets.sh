#!/usr/bin/env -S bash -eux

echo "Provisioning config files..."

set +x
if [ ! -e "/opt/manager/cloudify-rest.conf" ]; then
    echo "
postgresql_db_name: ${POSTGRES_DB}
postgresql_host: ${POSTGRES_HOST}
postgresql_username: ${POSTGRES_USER}
postgresql_password: ${POSTGRES_PASSWORD}
file_server_type: ${FILE_SERVER_TYPE}
" > /opt/manager/cloudify-rest.conf
fi

if [ ! -e "/opt/manager/rest-security.conf" ]; then
    # TODO: generate the encryption key, don't just hardcode it
    echo "
{
    \"secret_key\": \"${SECRET_KEY}\",
    \"hash_salt\": \"${HASH_SALT}\",
    \"encryption_key\": \"Fm89X7nuj-FvNB21jf5znIJylGXunva-RvK30756UPEBj0Bns0u-XY3XVGs6H8CAnGsiAI0tzcM0CbfbLcTk8Q==\"
}
" > /opt/manager/rest-security.conf
fi
set -x

echo "Config files provisioned!"

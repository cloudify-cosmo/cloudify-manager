#!/usr/bin/env -S bash -eux

/opt/rest-service/docker/prepare_secrets.sh

exec python -m manager_rest.configure_manager

#!/usr/bin/env -S bash -eux

exec \
  /opt/rest-service/docker/prepare_secrets.sh \
  & \
  python -m manager_rest.configure_manager

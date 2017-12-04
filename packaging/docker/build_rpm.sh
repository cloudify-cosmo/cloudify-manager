#!/usr/bin/env bash

set -eu

REMOTE_LOCATION='/root/cloudify-manager-install'

echo "Creating install RPM..."
chmod +x ${REMOTE_LOCATION}/packaging/create_rpm.sh
${REMOTE_LOCATION}/packaging/create_rpm.sh community true master ${REMOTE_LOCATION}
rpm -i /tmp/cloudify-manager-install*.rpm
rm -f /tmp/cloudify-manager-install*.rpm
rm -rf ${REMOTE_LOCATION}

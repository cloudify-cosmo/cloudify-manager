#!/usr/bin/env bash

set -eux

# Pick up path from circle, or use a default
REMOTE_LOCATION=${REMOTE_PATH:-/root/cloudify-manager-install}

echo "Creating install RPM..."
chmod +x ${REMOTE_LOCATION}/packaging/create_rpm
${REMOTE_LOCATION}/packaging/create_rpm --edition community --local-installer-path ${REMOTE_LOCATION}
rpm -i /tmp/cloudify-manager-install*.rpm
rm -f /tmp/cloudify-manager-install*.rpm
rm -rf ${REMOTE_LOCATION}

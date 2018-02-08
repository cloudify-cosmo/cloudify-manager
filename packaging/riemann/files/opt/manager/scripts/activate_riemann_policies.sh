#!/bin/bash -e
set -a
echo "Activating Riemann policies..."
. /etc/sysconfig/cloudify-mgmtworker
/opt/mgmtworker/env/bin/python /opt/manager/scripts/activate_riemann_policies

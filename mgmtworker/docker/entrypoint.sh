#!/usr/bin/env -S bash -eux

echo "Waiting for the admin token to be provisioned..."
until [ -f "/opt/mgmtworker/work/admin_token" ]; do
    sleep 1
done
echo "Found admin token!"

exec python -m mgmtworker.worker \
    --queue cloudify.management \
    --max-workers 10 \
    --hooks-queue cloudify-hooks

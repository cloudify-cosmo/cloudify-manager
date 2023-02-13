#!/usr/bin/env -S bash -eux

/opt/api-service/docker/prepare_secrets.sh

python -m manager_rest.configure_manager --db-wait postgresql

exec gunicorn \
  --pid /run/cloudify-api/pid \
  --chdir / \
  --workers $WORKER_COUNT \
  --max-requests $MAX_REQUESTS \
  --bind 0.0.0.0:$PORT \
  --timeout 300 \
  --access-logfile /var/log/cloudify/rest/audit.log \
  --access-logformat '%(t)s %(h)s %({X-Cloudify-Audit-Username}o)s %({X-Cloudify-Audit-Tenant}o)s %({X-Cloudify-Audit-Auth-Method}o)s "%(r)s" %(s)s %(b)s "%(a)s" took %(M)sms' \
  cloudify_api.main:app

#!/usr/bin/env -S bash -eux

/opt/rest-service/docker/prepare_secrets.sh

python -m manager_rest.configure_manager --db-wait $POSTGRES_HOST
python -m manager_rest.configure_manager --rabbitmq-wait rabbitmq

exec gunicorn \
  --pid /run/cloudify-restservice/pid \
  --chdir / \
  --workers $WORKER_COUNT \
  --max-requests $MAX_REQUESTS \
  --bind "$BIND_HOST:$PORT" \
  --timeout 300 \
  --access-logfile /var/log/cloudify/rest/audit.log \
  --access-logformat '%(t)s %(h)s %({X-Cloudify-Audit-Username}o)s %({X-Cloudify-Audit-Tenant}o)s %({X-Cloudify-Audit-Auth-Method}o)s "%(r)s" %(s)s %(b)s "%(a)s" took %(M)sms' \
  manager_rest.wsgi:app

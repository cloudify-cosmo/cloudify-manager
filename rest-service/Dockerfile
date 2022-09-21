# Run from source root
#
# Directory has to contain:
#  - cloudify-common
#  - cloudify-manager
#  - cloudify-rest.conf
#  - rest-security.conf

FROM python:3.10-slim

ENV WORKER_COUNT=0
ENV CPU_RATIO=0.2
ENV MAX_WORKER_COUNT=4
ENV MAX_REQUESTS=1000
ENV PORT=8101

RUN --mount=type=cache,target=/root/.cache apt-get update

RUN --mount=type=cache,target=/root/.cache apt-get install -y libpq-dev # Required for psycopg2
RUN --mount=type=cache,target=/root/.cache apt-get install -y gcc # Required for psycopg2
RUN --mount=type=cache,target=/root/.cache apt-get install -y libffi-dev # Required for cffi


WORKDIR /opt

# TODO: Change the way dependencies are installed
COPY cloudify-common cloudify-common
COPY cloudify-manager/rest-service rest-service

COPY cloudify-rest.conf /opt/manager/cloudify-rest.conf
COPY rest-security.conf /opt/manager/rest-security.conf

RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip

RUN --mount=type=cache,target=/root/.cache pip install -e cloudify-common[dispatcher]
RUN --mount=type=cache,target=/root/.cache pip install -e rest-service
RUN --mount=type=cache,target=/root/.cache pip install gunicorn

# Create log file
RUN mkdir -p /var/log/cloudify/rest
RUN touch /var/log/cloudify/rest/gunicorn.log

RUN adduser cfyuser
RUN rm -rf /run/cloudify-restservice/
RUN mkdir -p /run/cloudify-restservice
RUN chown cfyuser. /run/cloudify-restservice
RUN chmod 755 /run/cloudify-restservice

ENTRYPOINT gunicorn \
  -u cfyuser \
  -g cfyuser \
  --pid /run/cloudify-restservice/pid \
  --chdir / \
  --workers $WORKER_COUNT \
  --max-requests $MAX_REQUESTS \
  --bind 0.0.0.0:$PORT \
  --timeout 300 rest-service.manager_rest.wsgi:app \
  --log-file /var/log/cloudify/rest/gunicorn.log \
  --access-logfile /var/log/cloudify/rest/audit.log \
  --access-logformat '%(t)s %(h)s %({X-Cloudify-Audit-Username}o)s %({X-Cloudify-Audit-Tenant}o)s %({X-Cloudify-Audit-Auth-Method}o)s "%(r)s" %(s)s %(b)s "%(a)s" took %(M)sms'

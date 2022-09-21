FROM python:3.10-slim

ENV REST_HOST=manager
ENV REST_PORT=53333
ENV LOCAL_REST_CERT_FILE=/opt/mgmtworker/cloudify_internal_ca_cert.pem
ENV AGENT_WORK_DIR=/opt/mgmtworker
ENV MANAGER_NAME=cloudify-manager

RUN --mount=type=cache,target=/root/.cache apt-get update

RUN --mount=type=cache,target=/root/.cache apt-get install -y libpq-dev # Required for psycopg2
RUN --mount=type=cache,target=/root/.cache apt-get install -y gcc # Required for psycopg2
WORKDIR /opt

COPY . mgmtworker

COPY cloudify_internal_ca_cert.pem mgmtworker/cloudify_internal_ca_cert.pem
COPY cloudify-manager/resources/rest-service/cloudify/types manager/resources/cloudify/types

RUN --mount=type=cache,target=/root/.cache pip install --upgrade pip
RUN --mount=type=cache,target=/root/.cache pip install -r mgmtworker/requirements.txt
RUN --mount=type=cache,target=/root/.cache pip install mgmtworker/

ENTRYPOINT ["python", "-m", "mgmtworker.worker"]
CMD [\
  "--queue", "cloudify.management",\
  "--max-workers", "10",\
  "--hooks-queue", "cloudify-hooks"\
]

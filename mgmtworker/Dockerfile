# Run from source root (directory has to contain cloudify-common, cloudify-agent, cloudify-manager)

FROM python:3.10.6

RUN apt-get update
RUN pip install --upgrade pip

WORKDIR /usr/src/app

COPY cloudify-common cloudify-common
COPY cloudify-agent cloudify-agent
COPY cloudify-manager/mgmtworker mgmtworker
COPY cloudify-manager/workflows workflows

RUN pip install -e cloudify-common
RUN pip install -e cloudify-agent
RUN pip install -e mgmtworker
RUN pip install -e workflows
RUN pip install pyyaml
RUN pip install networkx==1.11

# For development purposes
RUN apt-get install -y nano

ENTRYPOINT ["python", "-m", "mgmtworker.worker"]
CMD [\
  "--queue", "cloudify.management",\
  "--max-workers", "10",\
  "--hooks-queue", "cloudify-hooks"\
]

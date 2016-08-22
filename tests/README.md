Cloudify Integration Tests
==========================

## Goal

This project aims to emulate a Cloudify Manager environment.
By doing that we can test a full Cloudify pipeline in an isolated environment, without using mocks (almost...).

# Setup

In this tutorial we will be installing a few Linux packages.
However, in order to make this tutorial as agnostic as possible to different linux distributions,
we will not be using Linux package managers, but rather compressed all-in-one distributions.
This also has the benefit of not adding and manipulating system wide configuration files.
It's best to create a dedicated directory for all of these packages, we will be using `~/dev/tools`.
Also, make sure you activate the virtualenv dedicated for Cloudify prior to running any install commands.

## Step 1: Install RabbitMQ Server

RabbitMQ is a Message broker written in Erlang. It serves as the message broker for our remote task execution engine (celery),
So, we need to [Install Erlang](https://www.erlang-solutions.com/downloads/download-erlang-otp) first.

Now we can install rabbit: <br>

```bash
~/dev/tools$ curl -L -O https://www.rabbitmq.com/releases/rabbitmq-server/v3.4.2/rabbitmq-server-generic-unix-3.4.2.tar.gz
~/dev/tools$ tar -xvf rabbitmq-server-generic-unix-3.4.2.tar.gz
```

Add the `~/dev/tools/rabbitmq_server-3.4.2/sbin` directory to your path. Verify this by starting a new shell and running: <br>

```bash
~/dev/tools$ which rabbitmq-server
```

## Step 2: Install Elasticsearch

Elasticsearch is our storage data store. To install it run:

```bash
~/dev/tools$ curl -L -O https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-1.4.2.tar.gz
~/dev/tools$ tar -xvf elasticsearch-1.4.2.tar.gz
```

Add the `~/dev/tools/elasticsearch-1.4.2/bin` directory to your path. Verify this by starting a new shell and running: <br>

```bash
~/dev/tools$ which elasticsearch
```

## Step 2.1 : Disable Elasticsearch multicast

By default, Elasticsearch is started with multicast enabled,
this can cause some strange behaviour when other instances of elasticsearch are running on the same network.
We want to disable this. To do so, open the `~/dev/tools/elasticsearch-1.4.2/config/elasticsearch.yml` file and **uncomment** this:

````yaml
#discovery.zen.ping.multicast.enabled: false
```

## Step 3: Install PostgreSQL

PostgreSQL is our DB.

You can install it using installer specific for you os. Installers can be found at [PostgreSQL Installers page] (http://www.bigsql.org/postgresql/installers.jsp)

Alternatively, you can install it manually.
* in CentOS:
```bash
~/dev/tools$ curl -L -O ftp://rpmfind.net/linux/centos/7.2.1511/os/x86_64/Packages/libxslt-1.1.28-5.el7.x86_64.rpm
~/dev/tools$ curl -L -O http://yum.postgresql.org/9.5/redhat/rhel-7-x86_64/postgresql95-9.5.3-2PGDG.rhel7.x86_64.rpm
~/dev/tools$ curl -L -O http://yum.postgresql.org/9.5/redhat/rhel-7-x86_64/postgresql95-contrib-9.5.3-2PGDG.rhel7.x86_64.rpm
~/dev/tools$ curl -L -O http://yum.postgresql.org/9.5/redhat/rhel-7-x86_64/postgresql95-libs-9.5.3-2PGDG.rhel7.x86_64.rpm
~/dev/tools$ curl -L -O http://yum.postgresql.org/9.5/redhat/rhel-7-x86_64/postgresql95-server-9.5.3-2PGDG.rhel7.x86_64.rpm
~/dev/tools$ curl -L -O http://yum.postgresql.org/9.5/redhat/rhel-7-x86_64/postgresql95-devel-9.5.3-2PGDG.rhel7.x86_64.rpm
~/dev/tools$ sudo rpm -Uvh libxslt-1.1.28-5.el7.x86_64.rpm
~/dev/tools$ sudo rpm -Uvh postgresql9*.rpm
~/dev/tools$ sudo /usr/pgsql-9.5/bin/postgresql95-setup initdb
```

* in Ubuntu:
```bash
~/dev/tools$ sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ `lsb_release -cs`-pgdg main" >> /etc/apt/sources.list.d/pgdg.list'
~/dev/tools$ wget -q https://www.postgresql.org/media/keys/ACCC4CF8.asc -O - | sudo apt-key add -
~/dev/tools$ sudo apt-get update
~/dev/tools$ sudo apt-get install postgresql postgresql-contrib
```

## Step 3.1: Configure PostgreSQL

* Define "pg_hba" environment variable that will contain the postgresql configuration file path:
 * in ubuntu, it'll be something like:
    ```pg_hba="/etc/postgresql/9.5/main/pg_hba.conf" ```
 * in RHEL/CentOS, it'll be something like:
    ```pg_hba="/var/lib/pgsql/9.5/data/pg_hba.conf" ```
 * can't find the file?
    * run:   ```locate pg_hba.conf```
    * or look around the postgres data folder. find the data folder using: ```sudo -u postgres psql -c "show data_directory"```

* Update postgres configuration file, to allow authentication with arbitrary users and passwords:
```bash
echo "Creating backup file $pg_hba.backup"
sudo cp $pg_hba $pg_hba.backup
echo "Going to modify $pg_hba"
sudo bash -c "cat $pg_hba | awk '/^host/{gsub(/ident/, \"md5\")}; {print}' > $pg_hba.tmp; cp $pg_hba.tmp $pg_hba"
```

* Start Postgres:
    * in Ubuntu:
    ```bash
    sudo systemctl stop postgresql
    sudo systemctl start postgresql
    ```
    * in CentOS:
    ```bash
    sudo systemctl stop postgresql-9.5.service
    sudo systemctl start postgresql-9.5.service
    ```

* Create cloudify user for Postgres:
```bash
sudo -u postgres psql
CREATE USER cloudify WITH PASSWORD 'cloudify';
ALTER USER cloudify CREATEDB;
\q
```

## Step 4: Installing Riemann

Riemann is a policy and event processing engine. We use it to create monitoring policies.

```bash
~/dev/tools$ wget http://aphyr.com/riemann/riemann-0.2.6.tar.bz2
~/dev/tools$ tar xvfj riemann-0.2.6.tar.bz2
```

Add the `~/dev/tools/riemann-0.2.6/bin` directory to your path. Verify this by starting a new shell and running: <br>

```bash
~/dev/tools$ which riemann
```

## Step 5: Installing riemann controller

The *riemann-controller* is a Cloudify plugin that configures riemann for our usage.
`cd` into the root directory of this repo (*cloudify-manager*) and run:

```bash
pip install -e plugins/riemann-controller/
```

## Step 6: Installing Workflows

The *workflows* project contains Cloudify system workflows, i.e, workflows that we use for managerial configuration.
Specifically, it contains workflows that create/delete deployments.
`cd` into the root directory of this repo (*cloudify-manager*) and run:

```bash
pip install -e workflows/
```

## Step 7: Installing REST service

The *rest-service* project is the REST gateway all clients connect to.
We will be running it as part of the tests, so we need install its dependencies.
`cd` into the root directory of this repo (*cloudify-manager*) and run:

```bash
pip install -r rest-service/dev-requirements.txt -e rest-service/
```

## Step 8: Installing tests framework

The tests in this project fork celery processes and we want these processes to have access to code written in the project (utility methods and such),
that's why we need to install it as well.
`cd` into the root directory of this repo (*cloudify-manager*) and run:

```bash
pip install -r tests/dev-requirements.txt -e tests/
```

## Step 9: Verify installation.

Lets verify everything works by running a test. First we need to start our RabbitMQ Server:

```bash
rabbitmq-server -detached
```

Now, `cd` into the root directory of this repo (*cloudify-manager*) and run:

```bash
nosetests -s tests/workflow_tests/test_workflow.py:BasicWorkflowsTest.test_execute_operation
```

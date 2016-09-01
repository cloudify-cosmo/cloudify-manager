Cloudify Integration Tests
==========================

## Goal
This project runs tests on a Cloudify Manager container created by `docl`.

## Setup
1. Install Docker. (https://docs.docker.com/engine/installation/).
   Make sure docker is installed but not running as a service.

2. The current implementation requires that docker is exposed on TCP rather than
   the usual unix socket so the following configuration is required. Note that
   we are going to create a custom bridge that will only be accessible by the host
   machine (your machine) and the containers. This is because we will be running
   docker with no security enabled so we don't want it exposed on external network
   interfaces because that would be quite bad.
   * Run the following to create a bridge named `cfy0` (Based off of https://docs.docker.com/engine/userguide/networking/default_network/build-bridges/)

     ```
     $ sudo brctl addbr cfy0
     $ sudo ip addr add 172.20.0.1/24 dev cfy0
     $ sudo ip link set dev cfy0 up
     ```

     **Note**: This process needs to be executed manually after every
     reboot. (unless automated somehow, which is not described here)

   * Run docker using the following flags. (You can probably configure the docker service
     on your OS to do that for you)

      ```
      $ sudo dockerd --bridge cfy0 --host 172.20.0.1
      ```
      Docker needs to run with sudo because containers are started with the `privileged`
      flag.
   * To be able to run `docker` commands, export the `DOCKER_HOST` environment
     variable.

     ```
     export DOCKER_HOST=172.20.0.1
     ```

3. The following cloudify-cosmo github repositories need to be cloned to
   some directory (`source_root`):
   
       * `cloudify-amqp-influxdb`
       * `cloudify-plugins-common`
       * `cloudify-agent`
       * `cloudify-rest-client`
       * `cloudify-dsl-parser`
       * `cloudify-manager`
       * `cloudify-script-plugin`
       * `flask-securest`
       * `cloudify-diamond-plugin`
       * `cloudify-cli`
   
   **Note**: You may want to consider using `clue`. (http://clue.readthedocs.io/en/latest/) 
   Which amongst other things, will also automate this process for you.
   
4. Inside a virtualenv, run:

   ```
   $ pip install nose
   $ pip install -e <SOURCE_ROOT>/cloudify-dsl-parser
   $ pip install -e <SOURCE_ROOT>/cloudify-rest-client
   $ pip install -e <SOURCE_ROOT>/cloudify-plugins-common
   $ pip install -e <SOURCE_ROOT>/cloudify-script-plugin
   $ pip install -e <SOURCE_ROOT>/cloudify-cli
   $ pip install -e <SOURCE_ROOT>/cloudify-manager/tests
   $ pip install -e <SOURCE_ROOT>/cloudify-agent
   $ pip install -e <SOURCE_ROOT>/cloudify-diamond-plugin
   ```

5. Configure `docl` (https://github.com/dankilman/docl). (`docl` is installed
   as a dependency of the integration tests project)
   1. run:

      ```
      $ docl init
      ```
      * `--source-root` should point to the root directory where all Cloudify
        repositories are cloned.
      * `--ssh-key-path` should be a private ssh key on your file system. This
        key will be used to connect to manager containers during the bootstrap
        process and when using `docl ssh`. Generate one if you don't already
        have one.
      * `--docker-host` should be 172.20.0.1 (the socket docker was
        initially started on)
      * `--simple-manager-blueprint-path` should point to a simple manager blueprint
        path. Preferably the one in your cloned `cloudify-manager-blueprints` repo
   2. run:

      ```
      $ docl bootstrap
      ```

   3. run:

      ```
      $ docl save-image
      ```

All done!

To test everything is working as it should, run:

```
$ cd <root directory of cloudify-manager repository>
$ nosetests -s tests/workflow_tests/test_workflow.py:BasicWorkflowsTest.test_execute_operation
```

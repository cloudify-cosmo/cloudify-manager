Cloudify Integration Tests
==========================

## Goal
This project runs tests on a Cloudify Manager container created by [`docl`](https://github.com/cloudify-cosmo/docl).

## Setup
1. Install [Docker](https://docs.docker.com/engine/installation/).
   Make sure docker is installed but not running as a service.

2. The current implementation requires that docker is exposed on TCP rather than
   the usual unix socket so the following configuration is required. Note that
   we are going to create a custom bridge that will only be accessible by the host
   machine (your machine) and the containers. This is because we will be running
   docker with no security enabled so we don't want it exposed on external network
   interfaces because that would be quite bad.
   * Run the following to create a bridge named `cfy0` (Based off of docker [docs] (https://docs.docker.com/engine/userguide/networking/default_network/build-bridges/), this isn't permanent)

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

       * `cloudify-common`
       * `cloudify-agent`
       * `cloudify-manager`
       * `cloudify-diamond-plugin`
       * `cloudify-cli`

   **Note**: You may want to consider using [`clue`](http://clue.readthedocs.io/en/latest/).
   Which amongst other things, will also automate this process for you.

4. Inside a virtualenv, run:

   ```
   $ pip install nose python-dateutil pytest
   $ pip install -e <SOURCE_ROOT>/cloudify-common
   $ pip install -e <SOURCE_ROOT>/cloudify-cli
   $ pip install -e <SOURCE_ROOT>/cloudify-manager/tests
   $ pip install -e <SOURCE_ROOT>/cloudify-manager/rest-service
   $ pip install -e <SOURCE_ROOT>/cloudify-agent
   $ pip install -e <SOURCE_ROOT>/cloudify-diamond-plugin
   ```

5. Configure [`docl`](https://github.com/cloudify-cosmo/docl). (`docl` is installed
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

Here'es all the commands together:

     sudo brctl addbr cfy0
     sudo ip addr add 172.20.0.1/24 dev cfy0
     sudo ip link set dev cfy0 up
     sudo dockerd --bridge cfy0 --host 172.20.0.1
     export DOCKER_HOST=172.20.0.1

## Running Tests

To test everything is working as it should, run:

```
$ cd <root directory of cloudify-manager repository>
$ pytest -s tests/integration_tests/tests/agentless_tests/test_workflow.py::BasicWorkflowsTest::test_execute_operation
```

### Saving the Cloudify Manager's logs
In order to save the logs for tests before the test environment is destroyed, specify the path via an environment variable as follows:

```
export CFY_LOGS_PATH_REMOTE=<YOUR-PATH-HERE>
```
This will save the logs where the tests are *actually* run.

You may also set `export SKIP_LOGS_EXTRACTION=True` if you'd like to skip extraction and keep the `tar.gz` log archives.

To skip saving logs for successful tests, run `export SKIP_LOG_SAVE_ON_SUCCESS=True`.

For example you may want to run this before running the tests:
 ```
export CFY_LOGS_PATH_REMOTE=/tmp/cfy_test_logs/
export SKIP_LOGS_EXTRACTION=True
export SKIP_LOG_SAVE_ON_SUCCESS=True
``` 

_Note: when running with the `itests-runner` you need to also provide a `CFY_LOGS_PATH_LOCAL` env var via:
`export CFY_LOGS_PATH_LOCAL=<YOUR-LOCAL-PATH>` as the test runs on containers and `CFY_LOGS_PATH_REMOTE` is the path inside the containers.
This will save the logs on your local storage (where you ran `itests-runner`) at the `CFY_LOGS_PATH_LOCAL` path._ 
## Using Docl
* To get an overview of different features supplied by docl, see the README at [`docl`'s](https://github.com/cloudify-cosmo/docl) repo.

* If you want to manaully start a manager container, run `docl run --mount`. The `--mount` flag will start the manager container with code running on your laptop, without it, you get a plain vanilla manager container.

* Run `docl ssh` to ssh into the most recently started container.

* Tests running in the integration tests will start and stop containers all the time. If tests are stopped halfway through, it is recommened that you run `docl clean` to remove left over containers. While this is not strictly required, every container is running a full blown manager on your laptop which is quite heavy in terms of resources consumed.

* From time to time, you may want to make small modifications to the manager image. To do so, run `docl run`, then `docl ssh` to make the required changes. Afterwards, run `docl save-image` to override the existing image with your changes. 

* All commands that operate on containers accept an optional `--container-id` flag, in case there is need to operate on a different container than the one most recently started. To get the id, run `docker ps` and locate the relevant container.

* To start a plain CentOS container that can be manually bootstrapped on, run `docl prepare`. An inputs file that is suitable for bootstrap will be generated as well as part of this command.

* By default, `docl run` uses a docker image named `cloudify/centos-manager:7`. There may be cases where you'll want modifications you made in `save-image` not to override the default image. In these cases, you can supply the `--tag` flag to the `save-image` command with your own name, and then, supply the same `--tag` flag when you run `docl run`.


## Remote Debugging

If you work with `IntelliJ` or `PyCharm` IDE, you can debug the container's rest-service code from your editor.

* First, you have to configure your remote debugger (you will probably have to do that only the first time):
   1. Enter your editor's Run/Debug Configuration.
   2. Add a new configuration, by using the default `Python Remote Debug`.
   3. Give your configuration a name of your choosing.
   4. Set `Local host name` to: `172.20.0.1`.
   5. Set `Port` to: `53100`.
   6. Set 'Path mapping' (may not be necessary, since it can be automatically detected):
      * Set `local path` to your local path to the `manager_rest` directory.
      * Set `remote path` to the container's `manager_rest` directory, which is probably:
      `/opt/manager/env/lib/python2.7/site-packages/manager_rest`.
   7. Press OK to save your configuration.
   
* Define the environment variable `DEBUG_MODE` to be anything you want, as long as it is not empty.
   * If you run the test(s) from your editor, set the environment variable in your test configuration:
   Enter `Run` -> `Edit Configurations` and edit the `Environment Variables` field.  Add a variable named `DEBUG_MODE` and set its value to be any non-empty string.
   * If you run the test(s) from a terminal, you must set the environment variable on the same terminal, i.e: `export DEBUG_MODE=yariv`.
* In your editor, mark breakpoints inside the rest-service code, wherever you choose.

* In your editor, start the debugger you have configured, by choosing it and press `Debug`.

* Run tests from your editor, or with the same terminal in which you have defined the environemt variable `DEBUG_MODE`.

* The test(s) will run until reaching a breakpoint and you will be able to debug from your editor.

* To turn off debug-mode, unset the `DEBUG_MODE` variable.  If you have defined it in your editor, remove it.  If you have exported it in your terminal, unset it or set it to an empty string on the same terminal, i.e:

  ```
  unset DEBUG_MODE
  ```
  
  or:
  
  ```
  export DEBUG_MODE=
  ```

## Framework Logs

To keep the integration tests framework logs after the tests has finished running, make sure the directory `/var/log/cloudify` exists with editing permissions to everyone.  This will allow the integration tests framework to save its logs into a file in this directory.  The logs of different runs will be concatenated with separators between them, date, time and test name to identify the run.  You do not have to worry about disk space consumed by the log file, its size is limited to 5 MB.  Beyonf that size, the file would be splitted, with a maximum of 5 older files, after the main one (each file limited to 5 MB, so in total the logs cannot exceed 30 MB).

Cosmo Workflows
---------------

## Goal

The purpose of this project is to test cosmo workflows (ruote) started by cosmo's `orchestrator` component.
The tests are written in python and the test environment starts a celery worker and a riemann server before running the tests.

For a test example see: `workflow_tests/test_workflow.py`


## Requirements

* Python 2.7 runtime.
* A running rabbitmq server.
* Riemann server installed (riemann executable available in path).
* cosmo.jar available in ../orchestrator/target (built using mvn package -Pall in orchestrator).


## Installation

The project's dependencies installation is done using setup.py:

```
virtualenv venv
source venv/bin/activate
python setup.py install
```


## Running The Tests

```
nosetests workflow_tests
```


## Plugins

Plugins used by tests should be stored in `plugins` (folder per plugin).

If a plugin needs to write files to disk, these should be written to a temporary directory available from `os.environ["TEMP_DIR"]`.

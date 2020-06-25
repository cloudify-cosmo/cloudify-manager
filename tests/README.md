Cloudify Integration Tests
==========================

## Running integration tests

1. Install cloudify-common, cloudify-cli, manager_rest, and the tests package.
2. Make sure you have a manager docker container, `docker load` it if necessary.
3. Run pytest, eg:
```
pytest -vxs integration_tests/tests/agentless_tests/test_workflow.py::BasicWorkflowsTest::test_execute_operation
```

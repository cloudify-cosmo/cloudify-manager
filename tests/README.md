Cloudify Integration Tests
==========================

## Running integration tests

1. Install cloudify-common, cloudify-cli, manager_rest, and the tests package.
2. Make sure you have a manager docker image, `docker load` it if necessary.
3. Run pytest, eg:
```
pytest -vxs integration_tests/tests/agentless_tests/test_workflow.py::BasicWorkflowsTest::test_execute_operation
```

## Useful pytest flags

We add several commandline arguments for pytest:

- `--tests-source-root` - points to a directory that contains repositories
  with Cloudify code (or symlinks to them). Those repositories will be
  mounted into the container and used for the tests.
- `--image-name` - name of the docker image to run (default:
  `cloudify-manager-aio:latest`). Can be from a docker repository.
- `--keep-container` - don't delete the container after the test is done.
- `--container-id` - use a pre-spawned container (might be from a separate
  test run that provided --keep-container) for this test. Use this to
  greatly increase iteration speed when working with the tests.
- `--k8s-namespace` - use the Kubernetes cluster (must be already spawned in
  that namespace) to run the test.
- `--lightweight` - run a container without optional services, making it
  lighter and faster

## Source code mounting

Repositories from "tests-source-root" are going to be mounted into the
in-container virtualenvs. The mount list is maintained on an as-needed
basis, and is in `tests/conftest.py`. Feel free to add more entries to
it, if there's some source mounting missing that you need.
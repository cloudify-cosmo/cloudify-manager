Integration Tests Blueprint
============================
## Goal
The following docl blueprint provides a solution for executing the Cloudify integration tests on an Openstack/AWS environment.


## Usage
Execution of the blueprint is done by using the Cloudify CLI and requires configuring of the blueprint inputs file beforehand.
* Install the latest Cloudify CLI inside your virtual environment.
* Set the test suites you'de like to run in the `docl-base-types.yaml` file under the `test_suites` input. The default will run all tests.
* Set your custom branch/organization names, also located under `docl-base-types.yaml` file accordingly.
* Enter your cloud provider credentials under `os-inputs.yaml`/`aws-inputs.yaml` depending on the cloud provider of your choice.
* Execute the following commands to execute the blueprint:
```
cd cloudify-manager
cfy use local
cfy install tests/integration_tests_blueprint/os-docl-machine-blueprint.yaml -i tests/integration_tests_blueprint/os-inputs.yaml --install-plugins
```
To uninstall the blueprint, run the following:
```
cd cloudify-manager
cfy uninstall --task-retries 10
```

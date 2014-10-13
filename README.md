# Cloudify Manager

This repository contains the following Cloudify components:

* Cloudify's manager REST service.
* Plugins:
	* agent-installer (linux).
	* plugin-installer (linux).
	* windows-agent-installer.
	* windows-plugin-installer.
	* riemann-controller.
* Integration tests.


## Running Integration Tests

Integration tests can found within the `tests` folder of this repository.

Prerequisites:

1. Linux operating system.

Running the tests:

3. Run `run-tests.sh run-integration-tests` 
	- Use the `run-tests.sh` script with care as its intended to be used with clean virtual machine.
	- In order to run integration tests on a development machine, follow the commands written in the `run-integration-tests` function and make sure to have a running instance of a RabbitMQ server.

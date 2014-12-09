# Cloudify Manager

This repository contains the following Cloudify components:

* Cloudify's manager REST service.
* Plugins:
	* [agent-installer (linux)](http://getcloudify.org/guide/3.1/plugin-linux-agent-installer.html).
	* [plugin-installer (linux)](http://getcloudify.org/guide/3.1/plugin-installer-plugin.html).
	* [windows-agent-installer](http://getcloudify.org/guide/3.1/plugin-windows-agent-installer.html).
	* [windows-plugin-installer](http://getcloudify.org/guide/3.1/plugin-installer-plugin.html).
	* riemann-controller.
* Integration tests.

# REST API Reference

See [here](http://getcloudify.org/guide/3.1/reference-rest-api.html).

## Running Integration Tests

Integration tests can found within the `tests` folder of this repository.

Prerequisites:

An Ubuntu operating system.

Running the tests:

Run `run-tests.sh run-integration-tests`
- Use the `run-tests.sh` script with care as its intended to be used with clean virtual machine.
- In order to run integration tests on a development machine, follow the commands written in the `run-integration-tests` function and make sure to have a running instance of a RabbitMQ server.

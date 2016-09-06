# Cloudify Manager

[![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-manager/tree/master.svg?style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-manager/tree/master)
[![Build Status](https://travis-ci.org/cloudify-cosmo/cloudify-manager.svg?branch=master)](https://travis-ci.org/cloudify-cosmo/cloudify-manager)

This repository contains the following Cloudify components:

* Cloudify's manager REST service.
* riemann-controller.
* Cloudify system-workflows
* Integration tests.

# REST API Reference

See [here](http://docs.getcloudify.org/api/).

## Running Integration Tests

Integration tests can found within the [`tests`](tests) folder of this repository.

Prerequisites:

An Ubuntu operating system.

Running the tests:

Run `run-tests.sh run-integration-tests`
- Use the `run-tests.sh` script with care as its intended to be used with clean virtual machine.
- In order to run integration tests on a development machine, follow the commands written in the `run-integration-tests` function and make sure to have a running instance of a RabbitMQ server.

Cloudify Integration Tests
==========================

## Goal

This project aims to emulate a Cloudify Manager environment.
By doing that we can test a full cloudify pipeline in an isolated environment, without using mocks (almost...).

**Note** <br>
In this tutorial we will be installing a few Linux packages.
However, in order to make this tutorial as agnostic as possible to different linux distributions,
we will not be using Linux package managers, but rather compressed all-in-one distributions.
This also has the benefit of not adding and manipulating system wide configuration files.
Its best to create a dedicated directory for all of these packages, we will be using `~/dev/tools`

## Step 1: Install RabbitMQ Server

RabbitMQ is a Message broker written in Erlang.
So we need to [install Erlang](https://www.erlang-solutions.com/downloads/download-erlang-otp) first.

Now we can install rabbit: <br>

```bash
~/dev/tools$ curl --silent --show-error --retry 5 https://www.rabbitmq.com/releases/rabbitmq-server/v3.4.2/rabbitmq-server-generic-unix-3.4.2.tar.gz -o rabbitmq-server-generic-unix-3.4.2.tar.gz
~/dev/tools$ tar -xvf rabbitmq-server-generic-unix-3.4.2.tar.gz
```

Add the `~/dev/tools/rabbitmq_server-3.4.2/sbin` directory to your path. Verify this by starting a new shell and running: <br>

```bash
~/dev/tools$ which rabbitmq-server
```

# Cloudify Manager

[![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-manager/tree/master.svg?style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-manager/tree/master)
[![Build Status](https://travis-ci.org/cloudify-cosmo/cloudify-manager.svg?branch=master)](https://travis-ci.org/cloudify-cosmo/cloudify-manager)
[![Code Health](https://landscape.io/github/cloudify-cosmo/cloudify-manager/master/landscape.svg?style=flat)](https://landscape.io/github/cloudify-cosmo/cloudify-manager/master)

This repository contains the following Cloudify components:

* Cloudify's manager REST service.
* riemann-controller.
* Cloudify system-workflows
* Integration tests.

# REST API Reference

See [here](http://docs.getcloudify.org/api/).

## Running Integration Tests

Integration tests can found within the [`tests`](tests) folder of this repository.
See [Integration Tests Readme](tests/README.md)
# Cloudify Manager Install
[![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-manager-install/tree/master.svg?style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-manager-install/tree/master)
[![Code Health](https://landscape.io/github/cloudify-cosmo/cloudify-manager-install/master/landscape.svg?style=flat)](https://landscape.io/github/cloudify-cosmo/cloudify-manager-install/master)

A new, simpler, way to install a Cloudify manager.
Runs in half the time, with a fraction of the frustration.
1000% satisfaction guaranteed.

## Usage
### Installation

In the local install, the only thing the user needs, is a single RPM.

The RPM is now live on S3 (community version can be found [here](https://github.com/cloudify-cosmo/cloudify-versions/blob/master/packages-urls/manager-install-rpm.yaml), the
premium can be found [here](https://github.com/cloudify-cosmo/cloudify-premium/blob/master/packages-urls/manager-install-rpm.yaml)).
You can download and install it, following the instructions below.

For those who wish to manually create their own RPM (for development purposes)
see below steps 1-6.

#### Creating the RPM

1. SSH into a clean VM (or a bare metal server, of course).
2. Download the [`create_rpm`](packaging/create_rpm) script to the machine
with:

`curl -L -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/master/packaging/create_rpm`

3. Give it executable permissions:

`chmod +x create_rpm`

4. Execute the script:

Note: For this to work you will either need an ssh key that can access cloudify-premium (premium) or cloudify-versions (community),
or you will need to export GITHUB_USERNAME and GITHUB_PASSWORD env vars.

`./create_rpm`

To build community, execute with:
`./create_rpm --edition community`

5. This will result in an rpm created in `/tmp/cloudify-manager-install-premium-1.0-1.x86_64.rpm` or `/tmp/cloudify-manager-install-community-1.0.1.x86_64.rpm`.

> Note that steps 1-6 may be performed on a machine other than the one
intended to serve as a Cloudify manager. It will be then up to the user
to ensure the `rpm` is then copied to the other machine.

#### Installing Cloudify Manager

6. `yum` install the rpm:

`sudo yum install -y /tmp/cloudify-manager-install-premium-1.0-1.x86_64.rpm`
or
`sudo yum install -y /tmp/cloudify-manager-install-community-1.0-1.x86_64.rpm`

7. This step extracts necessary files on the system and gives permissions to the
`/opt/cloudify/config.yaml` file. One of the files extracted is the
`cfy_manager` executable which will be used to actually install the manager.
8. Only the private and public IPs are necessary to install the manager,
and those can be provided directly to the executable like this:

`cfy_manager install --private-ip <PRIVATE-IP> --public-ip <PUBLIC-IP>`

If more configurations are necessary, you may edit the config file in:
`/opt/cloudify/config.yaml`.

9. After the command has finished, you should have a working manager,
with `cfy` installed for both the current user and `root`.

### Configuration
If you wish to change some configuration after install, just edit
`config.yaml` again and run `cfy_manager configure`. It takes about a minute.

### Teardown
At any point, you can run `cfy_manager remove`, which will remove everything
Cloudify related from the machine, except the installation code, that
will remain in `/opt/cloudify/config.yaml`, so that you will
have the ability to run `cfy_manager install` again.


## Goodies
* `cfy_manager install` and `cfy_manager configure` can be run as many times as
you like. The commands are completely idempotent.
* Want to reconfigure the manager, but don't want to drop the DB?
Set `"postgres": {"create_db": false}"` in the config file.
* Working in offline mode? No problem. `cfy_manager install` can be used as is,
assuming the RPM was somehow delivered to the machine.
* Detailed debug logs of the installation process are available in
`/var/log/cloudify/manager/cfy_manager.log`

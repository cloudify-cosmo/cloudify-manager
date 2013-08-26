## Getting Started with Cosmo ##

Cloudify Cosmo deploys, monitors and manages complex applications. It follows the [TOSCA spec](https://www.oasis-open.org/committees/tosca).

The current version of Cosmo runs on a vagrant machine, reads the application plan file, and orchestrates the application deployment and monitoring.
The [sample application](vagrant/test/python_webserver/python-webserver.yaml) starts and monitors an LXC machine with a python web server. 

### Requirements ###
- Build Status (master branch) [![Build Status](https://secure.travis-ci.org/CloudifySource/cosmo-manager.png?branch=master)](http://travis-ci.org/CloudifySource/cosmo-manager)
- Virtual Box (https://www.virtualbox.org/wiki/Downloads)
- Vagrant 1.2.6 (http://downloads.vagrantup.com)
- Vagrant snapshot plugin (To install simply run: `vagrant plugin install vagrant-vbox-snapshot`)

the
### Bootstrap Cosmo ###

The process of creating a new vagrant machine may take up to 20 minutes.

```
                       $ git clone https://github.com/CloudifySource/cosmo-manager.git
                       $ cd cosmo-manager/vagrant
cosmo-manager/vagrant  $ vagrant up
cosmo-manager/vagrant  $ vagrant snapshot take after-bootstrap-snapshot
cosmo-manager/vagrant  $ vagrant ssh
vagrant@cosmo-manager:~$ cd ~/cosmo-work
```

### Deploy the sample application ###

The cosmo shell script starts cosmo and executes the specified plan file. It will create a new lxc machine with a celery worker and install python web server on the lxc machine.
```
vagrant@cosmo-manager:~/cosmo-work$ ./cosmo.sh --dsl=/vagrant/test/python_webserver/python-webserver.yaml
```

Wait until the script prints the following message:
```
ManagerBoot Application has been successfully deployed (press CTRL+C to quit)
```

Pressing Ctrl+C will stop cosmo processes, but will not destroy the LXC machine.
The LXC ip address is 10.0.3.5 and the python web server listens on port 8888.
```
vagrant@cosmo-manager:~/cosmo-work$ wget -O /dev/stdout http://10.0.3.5:8888
```
You can terminate all LXC machines with:
```
vagrant@cosmo-manager:~/cosmo-work$ ./cosmo.sh undeploy
```

For commandline usage see `./cosmo.sh --help`

### Suspend/Restore Cosmo ###
To save the current running state of the vagrant machine and stop it use `vagrant suspend`.
To start the vagrant machine at its last running state `vagrant up`.

To restore the Vagrant Machine to its original state (just after bootstrap) `vagrant snapshot go after-bootstrap-snapshot`

### Teardown Cosmo ###
To delete the vagrant machine run `vagrant terminate`.
That means the next time you run `vagrant up` it will need another 20 minutes to bootstrap.

## Upgrade ##

### Upgrade Cosmo to latest version ###

In case a new version of cosmo was released, you will probably want to upgrade.
It a simple matter of replacing a jar file.

```
vagrant@cosmo-manager:~/cosmo-work$ export cosmo_version=0.1-RELEASE
vagrant@cosmo-manager:~/cosmo-work$ wget -O ~/cosmo-work/cosmo.jar https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/.m2/repository/org/cloudifysource/cosmo/orchestrator/${cosmo_version}/orchestrator-${cosmo_version}-all.jar
```

* To upgrade to the latest development code use `cosmo_vesrsion=${version}-SNAPHOT`.
* To upgrade to a new release use `cosmo_version=${version}-RELEALSE`.

### Upgrade Cosmo from code ###

First build a new cosmo.jar. Then use the shared directory between the host and vagrant to copy the new jar.

```
cosmo-manager          $ mvn package -Pall -DskipTests -f orchestrator/pom.xml
cosmo-manager          $ cd vagrant
cosmo-manager/vagrant  $ cp ../orchestrator/target/cosmo.jar cosmo.jar
cosmo-manager/vagrant  $ vagrant ssh
vagrant@cosmo-manager:~$ cp /vagrant/cosmo.jar ~/cosmo-work/cosmo.jar
```

### Upgrade the vagrant operating system ###
A default box called 'precise64' is automatically added.
This is a pre-built Ubuntu 12.04 Precise x86_64 for lxc providers.
To add more boxes see [a list of pre-packaged images for vagrant-lxc](https://github.com/fgrehm/vagrant-lxc/wiki/Base-boxes#available-boxes)


## Contribute to Cosmo ##

You will need Maven and Git in order to develop the cosmo project.

- Open a new bug or feature request in [JIRA](cloudifysource.atlassian.net) with the "cosmo" label

- clone this repo

```
cosmo-manager$ git clone https://github.com/CloudifySource/cosmo-manager.git
```

- make changes on a seperate branch named `feature/CLOUDIFY-XXXX` where XXXX is the JIRA ID.

- Run unit tests

```
cosmo-manager$ mvn test -f travis-pom.xml
```
    
- Run integration test

```
cosmo-manager        $ cd vagrant
cosmo-manager/vagrant$ python2.7 test/dsl_test.py
```

- Open a new pull request with the changes.

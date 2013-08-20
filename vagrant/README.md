# Running Cloudify Cosmo#

Cloudify Cosmo runs on a vagrant machine. 
The demo recipe uses Cosmo to start and monitor an LXC machine with a python web server. 

## Requirements ##

- Virtual Box (https://www.virtualbox.org/wiki/Downloads)
- Vagrant 1.2.6 (http://downloads.vagrantup.com)
- Vagrant snapshot plugin (To install simply run: `vagrant plugin install vagrant-vbox-snapshot`)

## Bootstrap Cosmo ##

The process of creating a new vagrant machine may take up to 20 minutes.

```
git clone https://github.com/CloudifySource/cosmo-manager.git
cd cosmo-manager/vagrant
vagrant up
vagrant snapshot take manager
```

## Teardown Cosmo ##
To delete the vagrant machine run `vagrant terminate`.
That means the next time you run `vagrant up` it will need another 20 minutes to bootstrap.

## Suspend Cosmo ##
To save the current running state of the machine and stop it use `vagrant suspend`.
To restore the machine use `vagrant up`.

## Deploy Application ##
This example will start a new lxc machine and install a simple python web server on that mahcine.
```
vagrant ssh
/home/vagrant/cosmo-work/cosmo --dsl=/vagrant/test/python_webserver/python-webserver.yaml
```

For commandline usage see `~/cosmo-work/cosmo --help`

## Undeploy Application ##

The undeploy command will destroy any vagrant lxc machines provisioned within the management machine.
```
vagrant ssh
/home/vagrant/cosmo-work/cosmo undeploy
```

To restore the Vagrant Machine to its original state (just after bootstrap):
```
vagrant snapshot go manager
```

## Upgrade Cosmo to latest version ##

In case a new version of cosmo was released, you will probably want to upgrade.
It a simple matter of replacing a jar file.

```
vagrant snapshot go manager
vagrant ssh
export cosmo_version=0.1_SNASHOT
wget -O /home/vagrant/cosmo.jar https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/.m2/repository/org/cloudifysource/cosmo/orchestrator/{cosmo_version}/orchestrator-{cosmo_version}-all.jar
```

## Upgrade Cosmo from code ##

First build a new cosmo.jar
```
git clone https://github.com/CloudifySource/cosmo-manager.git
cd cosmo-manager
mvn install -f travis-pom.xml
mvn install -Pall -f orchestrator/pom.xml -DskipTests
```

Vagrant creates a shared directory between the host and the guest. It is accessible on the guest machine in /vagrant, which is mounted to the cosmo-manager/vagrant folder.

```
vagrant snapshot go manager
cp ../orchestrator/target/cosmo.jar cosmo.jar
vagrant ssh
cp /vagrant/cosmo.jar /home/vagrant/cosmo.jar
```

## Using a different vagrant box operating system ##
A default box called 'precise64' is automatically added.
This is a pre-built Ubuntu 12.04 Precise x86_64 for lxc providers.
To add more boxes see [a list of pre-packaged images for vagrant-lxc](https://github.com/fgrehm/vagrant-lxc/wiki/Base-boxes#available-boxes)


Contribute
==========

You will need Maven and Git in order to develop the cosmo project.

- clone this repo.

        git clone https://github.com/CloudifySource/cosmo-manager.git

- make changes.
- make sure nothing is broken.
    
    Running unit and integration tests
        
        cd ..
        mvn clean install -f travis-pom.xml
    
    Running the example dsl    
        
        python2.7 test/dsl_test.py

- pull request

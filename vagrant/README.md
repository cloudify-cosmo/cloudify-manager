# Booting up the management machine #

This will create a vagrant host with all the necessary components for the cosmo management machine.

**All code/script snippets assume your current directory is the root of this file.**


Requirements
============

- Virtual Box (https://www.virtualbox.org/wiki/Downloads)
- Vagrant 1.2.6 (http://downloads.vagrantup.com)
- Vagrant snapshot plugin (vagrant plugin install vagrant-vbox-snapshot)

Run
====

- vagrant up.

    Note :

    This process may be very long (estimated time of 20 minutes) it is highly recommended that you create a snapshot of
    this machine immediately after it is finished.

        vagrant snapshot take manager

    To revert back to the snapshot

        vagrant snapshot go manager


- vagrant ssh.
- add vagrant boxes (optional)

    * A default box called 'precise64' is automatically added.
      This is a pre-built Ubuntu 12.04 Precise x86_64 for lxc providers.

    To add more boxes see a list of pre-packaged images for vagrant-lxc :
    https://github.com/fgrehm/vagrant-lxc/wiki/Base-boxes#available-boxes

- type cosmo --help to see the usage.

    Note :

    Vagrant by default creates a shared directory between the host and the guest.
    It is accessible on the guest machine in /vagrant, which is mounted to the root directory of the Vagrantfile.


Upgrade
======

In case a new version of cosmo was released, you will probably want to upgrade.
It a simple matter of replacing a jar file.


Default values are: working_dir="/home/vagrant" and cosmo_version="0.1-SNAPSHOT"
This values can be configued inside the Vagrantfile.
To update the cosmo management jar, just SSH into the management machine and run:

    - cd {working_dir}
    - rm cosmo.jar
    - wget https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/.m2/repository/org/cloudifysource/cosmo/orchestrator/{cosmo_version}/orchestrator-{cosmo_version}-all.jar
    - mv orchestrator-{cosmo_version}-all.jar cosmo.jar


Stop
====

There are 3 ways to stop the management machine:

Note that running "vagrant destroy" will completely terminate the environment,
and another bootstrapping process will be needed.
There is really no need for this since you can always go back to a clean machine using the snapshot mechanism.

   * vagrant suspend
   * vagrant halt
   * vagrant destroy (not recommended)

For more reading, please refer to:
http://docs-v1.vagrantup.com/v1/docs/getting-started/teardown.html


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

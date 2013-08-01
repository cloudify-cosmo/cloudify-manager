# Booting up the management machine #

This will create a vagrant host with all the necessary components for the cosmo management machine.

Clone this repo and cd into the current file directory.

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
- add vagrant boxes

    * A default box called 'precise64' is automatically added.
      This is a pre-built Ubuntu 12.04 Precise x86_64 for lxc providers.

    To add more boxes see a list of pre-packaged images for vagrant-lxc :
    https://github.com/fgrehm/vagrant-lxc/wiki/Base-boxes#available-boxes

- type cosmo --help to see the usage.

    Note :

    Vagrant by default creates a shared directory between the host and the guest.
    It is accessible on the guest machine in /vagrant, which is mounted to the root directory of the vagrant file.


Update
======

To update the cosmo management jar:

    - cd {working_dir}
    - rm orchestrator-0.1-SNAPSHOT-all.jar
    - wget wget https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/.m2/repository/org/cloudifysource/cosmo/orchestrator/0.1-SNAPSHOT/orchestrator-0.1-SNAPSHOT-all.jar

Stop
====

Take a look at the vagrant teardown method and choose the one you like:

http://docs-v1.vagrantup.com/v1/docs/getting-started/teardown.html

Please note that running "vagrant destroy" will completely terminate the environment,
and another bootstrapping process will be needed.
There is really no need for this since you can always go back to a clean machine using the snapshot mechanism.



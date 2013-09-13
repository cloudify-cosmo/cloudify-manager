import logging
import os
import shutil
from fabric.operations import local
from cosmo_fabric.runner import FabricRetryingRunner

__author__ = 'elip'

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

REMOTE_WORKING_DIR = "/home/vagrant/cosmo-work"


def get_remote_runner():

    host_config = {
        'user': 'vagrant',
        'host': '127.0.0.1',
        'port': 2222,
        'key': '~/.vagrant.d/insecure_private_key'
    }
    host_string = '%(user)s@%(host)s:%(port)s' % host_config
    key_filename = host_config['key']

    return FabricRetryingRunner(key_filename=key_filename, host_string=host_string)


def get_local_runner():
    return FabricRetryingRunner(local=True)


def get_logger(name):
    logger = logging.getLogger(name)
    logger.level = logging.DEBUG
    return logger


def update_cosmo_jar():
    vagrant_test_dir = os.path.abspath(os.path.join(__file__, os.pardir))
    vagrant_dir = os.path.abspath(os.path.join(vagrant_test_dir, os.pardir))
    manager_dir = os.path.abspath(os.path.join(vagrant_dir, os.pardir))

    local("cd {0} && vagrant up".format(vagrant_dir))

    # package the orchestrator
    local("cd {0}/orchestrator && mvn clean package -Pall".format(manager_dir))

    # copy to shared directory
    shutil.copyfile("{0}/orchestrator/target/cosmo.jar".format(manager_dir),
                    "{0}/vagrant/cosmo.jar".format(manager_dir))

    # replace orchestrator jar on the management host
    get_remote_runner().run("cd {0} "
                            "&& rm cosmo.jar "
                            "&& cp -r /vagrant/cosmo.jar .".format(REMOTE_WORKING_DIR))



import os
import tempfile
from worker_installer.tasks import FabricRetryingRunner

__author__ = 'idanm'

VAGRANT_MACHINE_IP = "10.0.0.5"
VAGRANT_PATH = os.path.join(tempfile.gettempdir(), "vagrant-vms")


def get_remote_runner():

    host_config = {
        'user': 'vagrant',
        'host': VAGRANT_MACHINE_IP,
        'port': 22,
        'key': '~/.vagrant.d/insecure_private_key'
    }
    host_string = '%(user)s@%(host)s:%(port)s' % host_config
    key_filename = host_config['key']

    return FabricRetryingRunner(key_filename=key_filename, host_string=host_string)


def get_local_runner():
    return FabricRetryingRunner(local=True)

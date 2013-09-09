import os
import shutil
import tempfile
import vagrant
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


def launch_vagrant(vm_id):

    print "launching a new vagrant machine to be used by test"

    vagrant_file = """

        Vagrant.configure("2") do |config|
            config.vm.box = "precise64"
            config.vm.network :private_network, ip: {0}
            config.vm.provision :shell, :inline => "sudo ufw disable"
        end

        """.format(VAGRANT_MACHINE_IP)

    v = get_vagrant(VAGRANT_PATH, vm_id)
    with open("{0}/Vagrantfile".format(v.root), 'w') as output_file:
        print "writing vagrant file to {0}/Vagrantfile".format(v.root)
        output_file.write(vagrant_file)

    # start the machine
    print "calling vagrant up"
    v.up()


def terminate_vagrant(vm_id):
    print "terminating vagrant machine"
    v = get_vagrant(VAGRANT_PATH, vm_id)
    v.destroy()
    shutil.rmtree(v)


def get_vagrant(vagrant_path, vm_id):
    vm_path = os.path.join(vagrant_path, vm_id)
    if not os.path.exists(vm_path):
        os.makedirs(vm_path)
    return vagrant.Vagrant(vm_path)


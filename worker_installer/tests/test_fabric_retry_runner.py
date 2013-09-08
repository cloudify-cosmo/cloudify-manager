import os
import tempfile
import vagrant
import shutil

__author__ = 'elip'

from worker_installer.tasks import FabricRetryingRunner


def run(runner):
    runner.run("ls -l")


def sudo(runner):
    runner.sudo("ls -l")


def put(runner):
    data = "test"
    file_path = tempfile.NamedTemporaryFile().name
    runner.put(data, file_path)


def get(runner):
    data = "test"
    file_path = tempfile.NamedTemporaryFile().name
    runner.put(data, file_path)
    output = runner.get(file_path)
    assert output == data


class TestLocalRunnerCase:

    """
    Tests the fabric runner localhost functioanllity.
    """

    RUNNER = None

    @classmethod
    def setup_class(cls):
        cls.RUNNER = FabricRetryingRunner(local=True)

    def test_run(self):
        yield run, self.RUNNER

    def test_sudo(self):
        """
        Note
        ====
        You can only run this if you are a passwordless sudo user on the local host.
        This is the case for vagrant machines, as well as travis machines.
        """
        yield sudo, self.RUNNER

    def test_put(self):
        yield put, self.RUNNER

    def test_get(self):
        yield get, self.RUNNER


class TestRemoteRunnerCase:

    VAGRANT_PATH = os.path.join(tempfile.gettempdir(), "vagrant-vms")
    VM_ID = "TestRemoteRunnerCase"
    V = None
    RUNNER = None

    @classmethod
    def setup_class(cls):

        host_config = {
            'user': 'vagrant',
            'host': "10.0.0.5",
            'port': 22,
            'key': '~/.vagrant.d/insecure_private_key'
        }
        host_string = '%(user)s@%(host)s:%(port)s' % host_config
        key_filename = host_config['key']

        cls.RUNNER = FabricRetryingRunner(key_filename=key_filename, host_string=host_string)

        print "launching a new vagrant machine to be used by test"

        vagrant_file = """

        Vagrant.configure("2") do |config|
            config.vm.box = "precise64"
            config.vm.network :private_network, ip: "10.0.0.5"
            config.vm.provision :shell, :inline => "sudo ufw disable"
        end

        """

        cls.V = cls._get_vagrant()
        with open("{0}/Vagrantfile".format(cls.V.root), 'w') as output_file:
            print "writing vagrant file to {0}/Vagrantfile".format(cls.V.root)
            output_file.write(vagrant_file)

        # start the machine
        print "calling vagrant up"
        cls.V.up()

    @classmethod
    def teardown_class(cls):
        print "terminating vagrant machine"
        cls.V.destroy()
        shutil.rmtree(cls.V.root)

    @classmethod
    def _get_vagrant(cls):
        vm_path = os.path.join(cls.VAGRANT_PATH, cls.VM_ID)
        if not os.path.exists(vm_path):
            os.makedirs(vm_path)
        return vagrant.Vagrant(vm_path)


    @classmethod
    def _status(cls, v, host_id):

        # we assume a single vm vagrant file
        v_status = v.status()
        status = v_status.itervalues().next()
        print "vagrant vm status is {0}".format(status)
        return status

    def test_run(self):
        yield run, self.RUNNER

    def test_sudo(self):
        yield sudo, self.RUNNER

    def test_put(self):
        yield put, self.RUNNER

    def test_get(self):
        yield get, self.RUNNER

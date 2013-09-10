import os
import random
import string
import tempfile
from worker_installer.tests import get_remote_runner, get_local_runner

__author__ = 'elip'


def _id_generator(self, size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def _test_run(runner):
    runner.run("ls -l")


def _test_sudo(runner):
    runner.sudo("ls -l")


def _test_put(runner):
    data = "test"
    file_path = tempfile.NamedTemporaryFile().name
    runner.put(data, file_path)


def _test_get(runner):
    data = "test"
    file_path = tempfile.NamedTemporaryFile().name
    runner.put(data, file_path)
    output = runner.get(file_path)
    assert output == data


def _test_put_sudo(runner):
    data = "test"
    # we need a path that needs sudo
    file_path = "/etc/default/test_put_sudo"
    runner.put(data, file_path, use_sudo=True)
    output = runner.get(file_path)
    # echo command adds a blank line at the end
    assert output == data + "\n"


def _test_put_to_non_existing_dir(runner):
    data = "test"
    # we need a path that needs sudo
    file_path = os.path.join(tempfile.NamedTemporaryFile().name, _id_generator(6))
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
        cls.RUNNER = get_local_runner()

    def test_run(self):
        _test_run(self.RUNNER)

    def test_sudo(self):
        """
        Note
        ====
        You can only run this if you are a passwordless sudo user on the local host.
        This is the case for vagrant machines, as well as travis machines.
        """
        _test_sudo(self.RUNNER)

    def test_put(self):
        _test_put(self.RUNNER)

    def test_get(self):
        _test_get(self.RUNNER)

    def test_put_sudo(self):
        _test_put_sudo(self.RUNNER)

    def test_put_to_non_existing_dir(self):
        _test_put_to_non_existing_dir(self.RUNNER)

    def test_put_to_non_existing_dir_sudo(self):
        data = "test"
        # we need a path that needs sudo
        file_path = os.path.join(tempfile.NamedTemporaryFile().name, _id_generator(6))
        self.RUNNER.put(data, file_path, use_sudo=True)
        output = self.RUNNER.get(file_path)
        # echo command adds a blank line at the end
        assert output == data + "\n"


class TestRemoteRunnerCase:

    VM_ID = "TestRemoteRunnerCase"
    RUNNER = None

    @classmethod
    def setup_class(cls):
        from vagrant_helper import launch_vagrant
        launch_vagrant(cls.VM_ID)
        cls.RUNNER = get_remote_runner()

    @classmethod
    def teardown_class(cls):
        from vagrant_helper import terminate_vagrant
        terminate_vagrant(cls.VM_ID)

    def test_run(self):
        _test_run(self.RUNNER)

    def test_sudo(self):
        _test_sudo(self.RUNNER)

    def test_put(self):
        _test_put(self.RUNNER)

    def test_get(self):
        _test_get(self.RUNNER)

    def test_put_sudo(self):
        _test_sudo(self.RUNNER)

    def test_put_to_non_existing_dir(self):
        _test_put_to_non_existing_dir(self.RUNNER)

    def test_put_to_non_existing_dir_sudo(self):
        data = "test"
        # we need a path that needs sudo
        file_path = os.path.join(tempfile.NamedTemporaryFile().name, _id_generator(6))
        self.RUNNER.put(data, file_path, use_sudo=True)
        output = self.RUNNER.get(file_path)
        assert output == data

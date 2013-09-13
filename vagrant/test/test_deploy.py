import unittest

__author__ = 'elip'

from test import update_cosmo_jar
from test import get_remote_runner, REMOTE_WORKING_DIR


class DeployDSLTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RUNNER = get_remote_runner()
        cls.RUNNER.max_retries = 0
        update_cosmo_jar()

    def test_deploy_python_webserver(self):

        timeout = 10 * 60

        self.RUNNER.run("{0}/cosmo.sh "
                        "--timeout={1} "
                        "--dsl=/vagrant/test/python_webserver/python-webserver.yaml "
                        "--non-interactive"
                        .format(REMOTE_WORKING_DIR, timeout))

        # check the webserver was actually deployed
        self.RUNNER.run("wget http://10.0.3.5:8888;")

        # undeploy
        self.RUNNER.run("{0}/cosmo.sh undeploy".format(REMOTE_WORKING_DIR))

        # make sure undeploy was completed
        try:
            self.RUNNER.get("/tmp/vagrant-vms/simple_web_server.webserver_host")
            self.fail("Expected file error")
        except BaseException:
            pass


if __name__ == '__main__':
    unittest.main()

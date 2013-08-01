import unittest
import sys

from fabric.context_managers import settings
from fabric.operations import local, run


__author__ = 'elip'


class VagrantBootTest(unittest.TestCase):

    HOST = "127.0.0.1"
    PORT = 2222
    USERNAME = "vagrant"
    KEY = "~/.vagrant.d/insecure_private_key"

    def test_bootstrap(self):

        local("vagrant up")

        host_string = "{0}@{1}:{2}".format(self.USERNAME, self.HOST, self.PORT)
        print host_string
        with settings(host_string=host_string,
                      key_filename=self.KEY,
                      disable_known_hosts=True):
            """
            This should install out python web server on 10.0.3.5 lxc agent.
            """
            run("/home/vagrant/cosmo-work/cosmo.sh -dsl=/vagrant/test/python_webserver/python-webserver.yaml",
                stdout=sys.stdout)

            run("wget http://10.0.3.5:8888")


if __name__ == '__main__':
    unittest.main()



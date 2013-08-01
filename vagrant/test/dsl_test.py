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

    def test_deploy_with_local_changes(self):
        host_string = "{0}@{1}:{2}".format(self.USERNAME, self.HOST, self.PORT)
        print host_string

        # package the orchestrator
        local("cd ../../orchestrator && mvn clean package -Pall")

        # copy to shared directory
        local("cd ../../orchestrator && cp -r target/cosmo.jar ../vagrant")

        with settings(host_string=host_string,
                      key_filename=self.KEY,
                      disable_known_hosts=True):

            # replace orchestrator jar on the management host
            run("cd /home/vagrant/cosmo-work "
                "&& rm cosmo.jar "
                "&& cp -r /vagrant/cosmo.jar .")

            """
            This should install out python web server on 10.0.3.5 lxc agent.
            """
            run("/home/vagrant/cosmo-work/cosmo.sh --dsl=/vagrant/test/python_webserver/python-webserver.yaml",
                stdout=sys.stdout)

            run("wget http://10.0.3.5:8888;")

if __name__ == '__main__':
    unittest.main()



#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

import unittest
import sys
import os
import shutil
from os.path import expanduser

from fabric.context_managers import settings
from fabric.operations import local, run


__author__ = 'elip'


class VagrantBootTest(unittest.TestCase):

    # ssh details for connecting to the management machine for your host
    SSH_CONFIG = {
        'host': '127.0.0.1',
        'port': 2222,
        'username': 'vagrant',
        'key': "{0}/.vagrant.d/insecure_private_key".format(expanduser('~'))
    }

    def test_deploy_with_local_changes(self):

        vagrant_test_dir = os.path.abspath(os.path.join(__file__, os.pardir))
        vagrant_dir = os.path.abspath(os.path.join(vagrant_test_dir, os.pardir))
        manager_dir = os.path.abspath(os.path.join(vagrant_dir, os.pardir))

        remote_working_dir = "/home/vagrant/cosmo-work"

        local("cd {0} && vagrant up".format(vagrant_dir))

        host_string = "{0}@{1}:{2}".format(self.SSH_CONFIG['username'],
                                           self.SSH_CONFIG['host'],
                                           self.SSH_CONFIG['port'])

        # package the orchestrator
        local("cd {0}/orchestrator && mvn clean package -Pall".format(manager_dir))

        # copy to shared directory
        shutil.copyfile("{0}/orchestrator/target/cosmo.jar".format(manager_dir),
                        "{0}/vagrant/cosmo.jar".format(manager_dir))

        with settings(host_string=host_string,
                      key_filename=self.SSH_CONFIG['key'],
                      disable_known_hosts=True):

            # replace orchestrator jar on the management host
            run("cd {0} "
                "&& rm cosmo.jar "
                "&& cp -r /vagrant/cosmo.jar .".format(remote_working_dir))

            """
            This should install out python web server on 10.0.3.5 lxc agent.
            """
            run("{0}/cosmo.sh --dsl=/vagrant/test/python_webserver/python-webserver.yaml --validate".format(
                remote_working_dir),
                stdout=sys.stdout)
            run("{0}/cosmo.sh --dsl=/vagrant/test/python_webserver/python-webserver.yaml".format(remote_working_dir),
                stdout=sys.stdout)
            try:
                run("{0}/cosmo.sh --dsl=/vagrant/test/corrupted_dsl.yaml --validate".format(remote_working_dir),
                    stdout=sys.stdout)
                sys.exit("Expected validation exception but none occurred")
            except BaseException:
                pass

            run("wget http://10.0.3.5:8888;")

if __name__ == '__main__':
    unittest.main()



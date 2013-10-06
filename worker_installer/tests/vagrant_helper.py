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

import os
import shutil
import tempfile
import vagrant
from worker_installer.tests import get_logger
from worker_installer.tests import VAGRANT_MACHINE_IP

__author__ = 'elip'

VAGRANT_PATH = os.path.join(tempfile.gettempdir(), "vagrant-vms")

logger = get_logger("VagrantHelper")


def launch_vagrant(vm_id, ran_id):

    logger.info("launching a new virtual machine")

    vagrant_file = """

        Vagrant.configure("2") do |config|
            config.vm.box = "precise64"
            config.vm.network :private_network, ip: '{0}'
            config.vm.provision :shell, :inline => "sudo ufw disable"
        end

        """.format(VAGRANT_MACHINE_IP)

    v = get_vagrant(VAGRANT_PATH, vm_id, ran_id)
    with open("{0}/Vagrantfile".format(v.root), 'w') as output_file:
        logger.info("writing vagrant file to {0}/Vagrantfile".format(v.root))
        output_file.write(vagrant_file)

    # start the machine
    logger.info("calling vagrant up")
    v.up()


def terminate_vagrant(vm_id, ran_id):
    logger.info("terminating vagrant machine")
    v = get_vagrant(VAGRANT_PATH, vm_id, ran_id)
    v.destroy()
    shutil.rmtree(v.root)


def get_vagrant(vagrant_path, vm_id, ran_id):
    vm_path = os.path.join(vagrant_path, "{0}-{1}".format(vm_id, ran_id))
    if not os.path.exists(vm_path):
        os.makedirs(vm_path)
    return vagrant.Vagrant(vm_path)


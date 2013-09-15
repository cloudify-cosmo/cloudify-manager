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

import logging
import os
import tempfile
from worker_installer.tasks import FabricRetryingRunner

__author__ = 'idanm'

VAGRANT_MACHINE_IP = "10.0.0.5"
VAGRANT_PATH = os.path.join(tempfile.gettempdir(), "vagrant-vms")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


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


def get_logger(name):
    logger = logging.getLogger(name)
    logger.level = logging.DEBUG
    return logger

#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
from cloudify.context import BootstrapContext

__author__ = 'idanmo'

import logging
import os
import random
import string
import tempfile
import uuid

from cloudify.mocks import MockCloudifyContext

VAGRANT_MACHINE_IP = "10.0.0.5"
MANAGER_IP = '10.0.0.1'
VAGRANT_PATH = os.path.join(tempfile.gettempdir(), "vagrant-vms")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def get_logger(name):
    logger = logging.getLogger(name)
    logger.level = logging.DEBUG
    return logger


def get_local_context():
    deployment_id = 'deployment-{0}'.format(str(uuid.uuid4())[:5])
    return MockCloudifyContext(
        deployment_id=deployment_id,
        properties={
            'worker_config': {
                'disable_requiretty': False
            }
        },
        runtime_properties={
            'ip': 'localhost'
        }
    )


def get_remote_context():
    node_id = 'node-{0}'.format(str(uuid.uuid4())[:5])
    return MockCloudifyContext(
        node_id=node_id,
        properties={
            'worker_config': {
                'user': 'vagrant',
                'host': VAGRANT_MACHINE_IP,
                'key': '~/.vagrant.d/insecure_private_key',
                'port': 2222
            },
        },
        runtime_properties={
            'ip': '127.0.0.1'
        },
        bootstrap_context=BootstrapContext({
            'cloudify_agent': {
                'min_workers': 2,
                'max_workers': 5,
                'user': 'john doe',
                'remote_execution_port': 2222
            }
        })
    )

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

"""
Vagrant provisioner tasks.
"""

from cosmo.celery import celery

import os
import vagrant
import tempfile
from celery.utils.log import get_task_logger

RUNNING = 'running'
VAGRANT_PATH = 'vagrant-vms'

logger = get_task_logger(__name__)

vagrant_path = os.path.join(tempfile.gettempdir(), VAGRANT_PATH)
if not os.path.exists(vagrant_path):
    os.makedirs(vagrant_path)
v = vagrant.Vagrant(vagrant_path)


@celery.task
def provision(vagrant_file, **kwargs):
    logger.info("provisioning vagrant machine:\n{0}".format(vagrant_file))
    with open("{0}/Vagrantfile".format(vagrant_path), 'w') as output_file:
        output_file.write(vagrant_file)


@celery.task
def start(**kwargs):
    logger.info('calling vagrant up')
    if status() != RUNNING:
        return v.up()
    logger.info('vagrant vm is already up')


def stop(**kwargs):
    logger.info('calling vagrant halt')
    if status() == RUNNING:
        return v.halt()
    logger('vagrant vm is not running')


@celery.task
def terminate(**kwargs):
    logger.info('calling vagrant destroy')
    return v.destroy()


def status():
    return v.status()


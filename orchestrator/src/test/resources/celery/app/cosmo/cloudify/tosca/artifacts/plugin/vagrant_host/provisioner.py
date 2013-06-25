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
VAGRANT_PATH = os.path.join(tempfile.gettempdir(), "vagrant-vms")

logger = get_task_logger(__name__)


def get_vagrant(vm_id, create=False):
    vm_path = os.path.join(VAGRANT_PATH, vm_id)
    if not os.path.exists(vm_path):
        if create:
            os.makedirs(vm_path)
        else:
            raise RuntimeError("vagrant vm with id [{0}] does not exist".format(vm_id))
    return vagrant.Vagrant(vm_path)


@celery.task
def provision(vagrant_file, __cloudify_id, **kwargs):
    logger.info('provisioning vagrant vm [id=%s, vagrant_file=\n%s]', __cloudify_id, vagrant_file)
    v = get_vagrant(__cloudify_id, True)
    with open("{0}/Vagrantfile".format(v.root), 'w') as output_file:
        output_file.write(vagrant_file)


@celery.task
def start(__cloudify_id, **kwargs):
    logger.info('calling vagrant up [id=%s]', __cloudify_id)
    v = get_vagrant(__cloudify_id)
    if status(v) != RUNNING:
        return v.up()
    logger.info('vagrant vm is already up [id=%s]', __cloudify_id)


def stop(__cloudify_id, **kwargs):
    logger.info('calling vagrant halt [id=%s]', __cloudify_id)
    v = get_vagrant(__cloudify_id)
    if status(v) == RUNNING:
        return v.halt()
    logger('vagrant vm is not running [id=%s]', __cloudify_id)


@celery.task
def terminate(__cloudify_id, **kwargs):
    logger.info("calling vagrant destroy [id=%s]", __cloudify_id)
    v = get_vagrant(__cloudify_id)
    return v.destroy()


def status(v):
    return v.status()


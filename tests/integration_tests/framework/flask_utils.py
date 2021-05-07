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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging

from cloudify.utils import setup_logger

from integration_tests.framework.docker import (execute,
                                                copy_file_to_manager)
from integration_tests.tests.constants import MANAGER_PYTHON
from integration_tests.tests.utils import get_resource


logger = setup_logger('Flask Utils', logging.INFO)
security_config = None

PREPARE_SCRIPT_PATH = '/tmp/prepare_reset_storage.py'
SCRIPT_PATH = '/tmp/reset_storage.py'
CONFIG_PATH = '/tmp/reset_storage_config.json'


def prepare_reset_storage_script(container_id):
    reset_script = get_resource('scripts/reset_storage.py')
    prepare = get_resource('scripts/prepare_reset_storage.py')
    copy_file_to_manager(container_id, reset_script, SCRIPT_PATH)
    copy_file_to_manager(container_id, prepare, PREPARE_SCRIPT_PATH)
    execute(container_id,
            [MANAGER_PYTHON, PREPARE_SCRIPT_PATH, '--config', CONFIG_PATH])


def reset_storage(container_id):
    logger.info('Resetting PostgreSQL DB')
    # reset the storage by calling a script on the manager, to access
    # localhost-only APIs (rabbitmq management api)
    execute(container_id,
            [MANAGER_PYTHON, SCRIPT_PATH, '--config', CONFIG_PATH])


def set_ldap(config_data):
    logger.info('Setting LDAP configuration')
    _prepare_set_ldap_script()
    execute("{manager_python} {script_path} --config '{cfg_data}'"
            .format(manager_python=MANAGER_PYTHON,
                    script_path='/tmp/set_ldap.py',
                    cfg_data=json.dumps(config_data)))


def _prepare_set_ldap_script():
    set_ldap_script = get_resource('scripts/set_ldap.py')
    copy_file_to_manager(set_ldap_script, '/tmp/set_ldap.py')

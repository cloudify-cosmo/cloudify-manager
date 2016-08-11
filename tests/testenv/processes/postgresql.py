########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import logging

from cloudify.utils import setup_logger

from . import utils


logger = setup_logger('postgresql_process')
PS_SERVICE_NAME = 'postgresql'


class PostgresqlProcess(object):
    """
    Manages an PostgreSQL lifecycle.
    """

    def __init__(self):
        self._on_ci = os.environ.get('CI') == 'true'
        setup_logger('postgresql', logging.INFO)
        setup_logger('postgresql.trace', logging.INFO)

    def start(self):
        if self._on_ci:
            logger.info('Running on CI, no need to start postgresql service..')
            return
        logger.info('Starting postgresql service...')
        utils.systemd.start(service_name=PS_SERVICE_NAME)
        logger.info('Verifying postgresql service is up...')
        if not utils.systemd.is_alive(service_name=PS_SERVICE_NAME):
            logger.warning('postgresql service is down!!!')

    def close(self):
        if self._on_ci:
            logger.info('Running on CI, not stopping postgresql')
            return
        logger.info('Stopping postgresql service...')
        utils.systemd.stop(service_name=PS_SERVICE_NAME)

    def configure(self):
        if self._on_ci:
            logger.info('Running on CI, postgresql been configured on run-tests beginning..')
            return
        logger.info('Configuring postgresql db..')
        ps_config_source = 'tests/postgresql_configuration.sh'
        ps_config_destination = '/tmp/postgresql_configuration.sh'
        utils.copy(source=ps_config_source,
                   destination=ps_config_destination)
        utils.sudo('chmod +x {0}'.format(ps_config_destination))
        utils.sudo('su - postgres -c {0}'.format(ps_config_destination))

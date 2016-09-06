########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
import uuid

import sh

from integration_tests import ManagerTestCase
from integration_tests.utils import get_resource as resource
from integration_tests.utils import wait_for_execution_to_end


class TestCeleryRestart(ManagerTestCase):

    STATUS_RETRY_COUNT = 10

    def test_execution_starts_after_mgmtworker_restart(self):
        self.run_manager()
        self._stop_celery()
        execution = self._create_execution()
        self._start_celery()
        wait_for_execution_to_end(execution)

    def _create_execution(self):
        blueprint_id = str(uuid.uuid4())
        deployment_id = blueprint_id
        blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.client.blueprints.upload(
            blueprint_path=blueprint_path,
            blueprint_id=blueprint_id)
        self.client.deployments.create(
            blueprint_id=blueprint_id,
            deployment_id=deployment_id)
        return self.client.executions.list(deployment_id=deployment_id)[0]

    def _stop_celery(self):
        self.logger.info('Stopping mgmtworker')
        self._service('stop')
        self.execute_on_manager('systemctl stop cloudify-mgmtworker')
        for _ in xrange(self.STATUS_RETRY_COUNT):
            try:
                self._service('status')
                time.sleep(1)
            except sh.ErrorReturnCode:
                return
        self.fail('Unable to stop mgmtworker')

    def _start_celery(self):
        self.logger.info('Starting mgmtworker')
        self._service('start')
        for _ in xrange(self.STATUS_RETRY_COUNT):
            try:
                self._service('status')
                return
            except sh.ErrorReturnCode:
                time.sleep(1)
        self.fail('Unable to start mgmtworker')

    def _service(self, action):
        self.execute_on_manager(
            'systemctl {0} cloudify-mgmtworker'.format(action))

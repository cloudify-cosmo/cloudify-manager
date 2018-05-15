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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid

from cloudify_rest_client import exceptions

from integration_tests import AgentTestCase
from integration_tests.framework.constants import CLOUDIFY_USER
from integration_tests.tests.utils import get_resource as resource
from integration_tests.tests.utils import \
    wait_for_deployment_creation_to_complete


class ManagerMaintenanceModeTest(AgentTestCase):
    def setUp(self):
        super(ManagerMaintenanceModeTest, self).setUp()
        # Only chowning the /opt/manager folder to allow creating the
        # maintenance folder. Not doing chown -R to avoid touching the
        # read-only /opt/manager/env folder
        self.env.chown(CLOUDIFY_USER, '/opt/manager', recursive=False)

    def test_maintenance_mode(self):
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        deployment_id = blueprint_id
        blueprint_path = resource('dsl/agent_tests/maintenance_mode.yaml')
        self.client.blueprints.upload(blueprint_path,
                                      entity_id=blueprint_id)
        self.client.deployments.create(blueprint_id=blueprint_id,
                                       deployment_id=deployment_id)
        wait_for_deployment_creation_to_complete(deployment_id=deployment_id)

        # Running none blocking installation
        execution = self.client.executions.start(deployment_id=deployment_id,
                                                 workflow_id='install')

        self.logger.info(
            "checking if maintenance status has status 'deactivated'")
        self._check_maintenance_status('deactivated')

        self.logger.info('activating maintenance mode')
        self.client.maintenance_mode.activate()
        self.addCleanup(self.cleanup)

        self.logger.info(
            "checking if maintenance status has changed to 'activating'")
        self.do_assertions(self._check_maintenance_status, timeout=60,
                           status='activating')

        self.logger.info('cancelling installation')
        self.cfy.executions.cancel(execution['id'])

        self.logger.info(
            "checking if maintenance status has changed to 'activated'")
        self.do_assertions(self._check_maintenance_status, timeout=60,
                           status='activated')

        self.logger.info('deactivating maintenance mode')
        self.client.maintenance_mode.deactivate()
        self.logger.info(
            "checking if maintenance status has changed to 'deactivated'")
        self.do_assertions(self._check_maintenance_status, timeout=60,
                           status='deactivated')

    def _check_maintenance_status(self, status):
        self.assertEqual(status, self.client.maintenance_mode.status().status)

    def cleanup(self):
        try:
            self.client.maintenance_mode.deactivate()
        except exceptions.NotModifiedError:
            pass

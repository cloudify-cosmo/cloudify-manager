########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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
import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
class TestDeploymentCreation(AgentlessTestCase):

    """Create multiple deployments."""

    DEPLOYMENTS_COUNT = 10

    def test_deployment_with_the_same_id(self):
        """Create multiple deployments with the same ID.

        The goal of this test is run multiple create/delete deployment cycles
        to find out if there's any race condition that prevents the creation of
        a deployment of the same ID just after it's been deleted.

        """
        dsl_path = utils.get_resource('dsl/basic.yaml')
        blueprint_id = deployment_id = 'd{0}'.format(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, blueprint_id)
        utils.wait_for_blueprint_upload(blueprint_id, self.client)

        for _ in range(self.DEPLOYMENTS_COUNT):
            self.client.deployments.create(
                blueprint_id, deployment_id, skip_plugins_validation=True)
            utils.wait_for_deployment_creation_to_complete(
                 self.env.container_id,
                 deployment_id,
                 self.client
            )
            self.client.deployments.delete(deployment_id)
            utils.wait_for_deployment_deletion_to_complete(
                deployment_id, self.client
            )

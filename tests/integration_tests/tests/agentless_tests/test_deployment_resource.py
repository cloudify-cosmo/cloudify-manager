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

import tempfile
import uuid
from os.path import join

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.framework.constants import CLOUDIFY_USER
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_deployment_deletion_to_complete
)

from manager_rest.constants import DEFAULT_TENANT_NAME


RESOURCE_PATH = 'resources/resource.txt'
RESOURCE_CONTENT = b'this is a deployment resource'


@pytest.mark.usefixtures('testmockoperations_plugin')
class DeploymentResourceTest(AgentlessTestCase):

    def test_get_and_download_deployment_resource(self):
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        deployment_id = blueprint_id
        blueprint_path = resource('dsl/deployment_resource.yaml')
        base_dep_dir = '/opt/manager/resources/deployments'
        dep_dir = join(base_dep_dir, DEFAULT_TENANT_NAME, deployment_id)
        full_resource_path = join(base_dep_dir,
                                  DEFAULT_TENANT_NAME,
                                  deployment_id,
                                  RESOURCE_PATH)
        self.execute_on_manager('mkdir -p {0}/resources'.format(dep_dir))

        with tempfile.NamedTemporaryFile() as f:
            f.write(RESOURCE_CONTENT)
            f.flush()
            self.copy_file_to_manager(source=f.name,
                                      target=full_resource_path)
            self.execute_on_manager('chmod +r {0}'.format(full_resource_path))

        # Everything under /opt/manager should be owned be the rest service
        self.execute_on_manager(
            'chown -R {0}. {1}'.format(CLOUDIFY_USER, dep_dir)
        )

        deployment, _ = self.deploy_application(
            blueprint_path,
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            inputs={'resource_path': RESOURCE_PATH})

        node_instance = self.client.node_instances.list(
            deployment_id=deployment.id)[0]

        get_resource_content = node_instance.runtime_properties['get_resource']
        download_resource_path = \
            node_instance.runtime_properties['download_resource']

        resource_content = RESOURCE_CONTENT.decode('utf-8')
        self.assertEquals(resource_content,
                          get_resource_content)
        self.assertEquals(resource_content,
                          self.read_manager_file(download_resource_path))

        self.client.deployments.delete(deployment_id, force=True)
        wait_for_deployment_deletion_to_complete(deployment_id, self.client)
        # TODO there is a bug when trying to delete deployment using
        #  --force flag where the main directory of current deployment
        #  `/opt/manager/resources/deployments/default_tenant/DEPLOYMENT_ID`
        #  still there where it should be deleted
        # self.assertRaises(
        #     sh.ErrorReturnCode,
        #     self.execute_on_manager,
        #     'test -d {0}'.format(dep_dir))

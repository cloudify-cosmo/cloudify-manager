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
from subprocess import CalledProcessError
from os.path import join

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_deployment_deletion_to_complete
)

pytestmark = pytest.mark.group_deployments
RESOURCE_PATH = 'resources/resource.txt'
RESOURCE_CONTENT = 'this is a deployment resource'
UPDATED_CONTENT = 'this is an updated deployment resource'


@pytest.mark.usefixtures('testmockoperations_plugin')
class DeploymentResourceTest(AgentlessTestCase):

    def test_get_and_download_deployment_resource(self):
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        deployment_id = blueprint_id
        blueprint_path = resource('dsl/deployment_resource.yaml')
        base_dep_dir = '/opt/manager/resources/deployments'
        dep_resources_dir = join(
            base_dep_dir,
            'default_tenant',
            deployment_id,
            'resources'
        )
        full_resource_path = join(base_dep_dir,
                                  'default_tenant',
                                  deployment_id,
                                  RESOURCE_PATH)
        self.execute_on_manager('mkdir -p {0}'.format(dep_resources_dir))
        self.execute_on_manager(f'chown -R cfyuser. {base_dep_dir}')
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(RESOURCE_CONTENT)
            f.flush()
            self.copy_file_to_manager(source=f.name,
                                      target=full_resource_path)
            self.execute_on_manager('chmod +rx {0}'.format(
                full_resource_path))

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

        self.assertEqual(RESOURCE_CONTENT,
                         get_resource_content)
        self.assertEqual(RESOURCE_CONTENT,
                         self.read_manager_file(download_resource_path))

        self.client.deployments.delete(
            deployment_id,
            force=True,
            delete_db_mode=True
        )
        wait_for_deployment_deletion_to_complete(deployment_id, self.client)
        with pytest.raises(CalledProcessError):
            self.execute_on_manager('test -d {0}'.format(dep_resources_dir))

    def test_deployment_resource_crud(self):
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        deployment_id = 'resource-crud'
        blueprint_path = resource('dsl/deployment_resource_crud.yaml')
        base_dep_dir = '/opt/manager/resources/deployments'
        dep_resources_dir = join(
            base_dep_dir,
            'default_tenant',
            deployment_id,
            'resources'
        )
        full_resource_path = join(base_dep_dir,
                                  'default_tenant',
                                  deployment_id,
                                  RESOURCE_PATH)
        self.execute_on_manager('mkdir -p {0}'.format(dep_resources_dir))
        self.execute_on_manager(f'chown -R cfyuser. {base_dep_dir}')
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(RESOURCE_CONTENT)
            f.flush()
            self.copy_file_to_manager(source=f.name,
                                      target=full_resource_path)
            self.execute_on_manager('chmod +rx {0}'.format(
                full_resource_path))

        deployment, _ = self.deploy_application(
            blueprint_path,
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            inputs={
                'resource_path': 'resources/crud-test.txt',
                'removed_in_the_middle_file_path': RESOURCE_PATH,
                'resource_content': RESOURCE_CONTENT,
                'updated_content': UPDATED_CONTENT,
            })

        test_resource_path = join(base_dep_dir,
                                  'default_tenant',
                                  deployment_id,
                                  'resources/crud-test.txt')

        # check if test_resource_path is uploaded and contains UPDATED_CONTENT
        self.execute_on_manager('test -f {0}'.format(test_resource_path))
        _, tmp_file_name = tempfile.mkstemp()
        self.copy_file_from_manager(source=test_resource_path,
                                    target=tmp_file_name)

        with open(tmp_file_name) as test_file:
            assert test_file.read().strip() == UPDATED_CONTENT

        # Remove the file on the manager and run a workflow which will check if
        # it was removed from the mgmtworker's resources directory
        self.execute_on_manager(f'rm {full_resource_path}')
        self.execute_workflow('uninstall', deployment_id)

        # check that test_resource_path does not exist on manager
        with pytest.raises(CalledProcessError):
            self.execute_on_manager('test -f {0}'.format(test_resource_path))

        self.client.deployments.delete(deployment_id)
        wait_for_deployment_deletion_to_complete(deployment_id, self.client)
        with pytest.raises(CalledProcessError):
            self.execute_on_manager('test -d {0}'.format(dep_resources_dir))

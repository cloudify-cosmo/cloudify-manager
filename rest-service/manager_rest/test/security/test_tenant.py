#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from nose.plugins.attrib import attr

from manager_rest.test.base_test import LATEST_API_VERSION

from .test_base import BaseServerTestCase


@attr(client_min_version=2, client_max_version=LATEST_API_VERSION)
class AuthenticationTests(BaseServerTestCase):

    def test_default_tenant(self):
        self.put_deployment()
        self.upload_plugin('psutil', '3.3.0')

        blueprint = self.sm.list_blueprints()[0]
        self.assertEqual(blueprint.id, 'blueprint')
        self.assertEqual(blueprint.tenant.name, 'default_tenant')

        deployment = self.sm.list_deployments()[0]
        self.assertEqual(deployment.id, 'deployment')
        self.assertEqual(deployment.tenant.name, 'default_tenant')

        execution = self.sm.list_executions()[0]
        self.assertEqual(execution.workflow_id,
                         'create_deployment_environment')
        self.assertEqual(execution.tenant.name, 'default_tenant')

        plugin = self.sm.list_plugins()[0]
        self.assertEqual(plugin.package_source, 'psutil==3.3.0')
        self.assertEqual(plugin.tenant.name, 'default_tenant')

        provider_context = self.sm.get_provider_context()
        self.assertEqual(provider_context.tenant.name, 'default_tenant')

# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import mock

from cloudify.constants import SHARED_RESOURCE
from cloudify.exceptions import NonRecoverableError

from .base_test_suite import TestSharedResourceBase
from cloudify_types.component.constants import CAPABILITIES
from ..operations import connect_deployment, disconnect_deployment


class TestSharedResource(TestSharedResourceBase):

    @mock.patch('cloudify_types.shared_resource.shared_resource'
                '.get_deployment_by_id',
                return_value=True)
    def test_runtime_props_set_after_successful_connection(self, mock_client):
        self.cfy_mock_client.deployments.capabilities.get = \
            mock.MagicMock(return_value={
                CAPABILITIES:
                    {'test': 1}
            })
        mock_client.return_value = self.cfy_mock_client

        connect_deployment()
        self.assertIn('deployment',
                      self._ctx.instance.runtime_properties)
        self.assertEqual(
            self._ctx.instance.runtime_properties['deployment']['id'],
            'test_deployment')

        self.cfy_mock_client.inter_deployment_dependencies.create \
            .assert_called_with(
                dependency_creator='{0}.{1}'.format(
                    SHARED_RESOURCE, self._ctx.instance.id),
                source_deployment=self._ctx.deployment.id,
                target_deployment='test_deployment'
            )
        self.assertEqual(
            {'test': 1},
            (self._ctx.instance.runtime_properties[CAPABILITIES]))

    @mock.patch('cloudify_types.shared_resource.shared_resource'
                '.get_deployment_by_id',
                return_value=False)
    def test_validate_deployment_fails_when_deployment_doesnt_exist(self, _):
        self.assertRaisesRegex(NonRecoverableError,
                               r'SharedResource\'s deployment ID '
                               r'"test_deployment" does not exist.*',
                               connect_deployment)
        self.assertNotIn('deployment',
                         self._ctx.instance.runtime_properties)
        self.cfy_mock_client.inter_deployment_dependencies.create \
            .assert_not_called()

    @mock.patch('cloudify_types.shared_resource.shared_resource'
                '.get_deployment_by_id',
                return_value=True)
    def test_disconnecting_deployment_removes_deployment_dependency(self, _):
        disconnect_deployment()

        self.cfy_mock_client.inter_deployment_dependencies.delete \
            .assert_called_with(
                dependency_creator='{0}.{1}'.format(
                    SHARED_RESOURCE, self._ctx.instance.id),
                source_deployment=self._ctx.deployment.id,
                target_deployment='test_deployment'
            )

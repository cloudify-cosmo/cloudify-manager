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

import datetime

from mock import MagicMock, Mock

from cloudify_rest_client.responses import ListResponse


class BaseMockClient(object):
    existing_objects = []

    def set_existing_objects(self, existing_objects):
        self.existing_objects = existing_objects

    def list(self, *_, **__):
        response = ListResponse(self.existing_objects,
                                metadata={
                                    "pagination":
                                        {"total": len(self.existing_objects),
                                         "offset": len(self.existing_objects)
                                         }
                                })
        return response

    def delete(self, *_, **__):
        return None


class MockBlueprintsClient(BaseMockClient):

    def _upload(self, *_, **__):
        return MagicMock(return_value={'id': 'test'})

    def get(self, *_, **__):
        return {'state': 'uploaded'}


class MockDeploymentsClient(BaseMockClient):

    def __init__(self):
        super(MockDeploymentsClient, self).__init__()
        self.capabilities = MockDeploymentCapabilitiesClient()

    def create(self, *_, **__):
        _return_value = {
            'id': 'test',
            'created_at': datetime.datetime.now()
        }
        return MagicMock(_return_value)


class MockExecutionsClient(BaseMockClient):

    def start(self, *_, **__):
        _return_value = {
            'id': 'test',
            'created_at': datetime.datetime.now()
        }
        return MagicMock(_return_value)

    def get(self, *_, **__):
        return {
            'id': MagicMock,
            'deployment_id': MagicMock,
            'status': MagicMock,
            'workflow_id': MagicMock,
        }


class MockEventsClient(BaseMockClient):
    pass


class MockSecretsClient(BaseMockClient):
    pass


class MockDeploymentCapabilitiesClient(BaseMockClient):

    def get(self, *args, **_):
        return MagicMock(return_value={'capabilities': dict()})


class MockCloudifyRestClient(object):

    def __init__(self):
        self.blueprints = MockBlueprintsClient()
        self.deployments = MockDeploymentsClient()
        self.executions = MockExecutionsClient()
        self.events = MockEventsClient()
        self.secrets = MockSecretsClient()
        self.plugins = MagicMock()
        self.inter_deployment_dependencies = Mock()

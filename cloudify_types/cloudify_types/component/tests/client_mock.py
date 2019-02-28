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

from mock import MagicMock

from cloudify_rest_client.responses import ListResponse


class BaseMockClient(object):

    @property
    def list_mock(self):
        return {
            'id': MagicMock,
            'workflow_id': MagicMock,
            'workflow_state': MagicMock,
            'status': MagicMock
        }

    def base_list_return(self, *args, **_):
        del args
        return ListResponse([self.list_mock], metadata={})

    def list(self, *args, **kwargs):
        return self.base_list_return(args, kwargs)


class MockBlueprintsClient(BaseMockClient):

    def _upload(self, *args, **_):
        del args
        return MagicMock(return_value={'id': 'test'})

    def delete(self, *_, **__):
        return None


class MockDeploymentsOutputsClient(BaseMockClient):

    def get(self, *args, **_):
        del args
        return MagicMock(return_value={'outputs': {}})


class MockDeploymentsClient(BaseMockClient):

    def __init__(self):
        self.outputs = MockDeploymentsOutputsClient()

    def create(self, *args, **_):
        _return_value = \
            {
                'id': 'test',
                'created_at': datetime.datetime.now()
            }
        del args
        return MagicMock(_return_value)

    def delete(self, *args, **_):
        return


class MockExecutionsClient(BaseMockClient):

    def start(self, *args, **_):
        _return_value = \
            {
                'id': 'test',
                'created_at': datetime.datetime.now()
            }
        del args
        return MagicMock(_return_value)

    def get(self, *args, **_):
        del args
        return {
            'id': MagicMock,
            'deployment_id': MagicMock,
            'status': MagicMock,
            'workflow_id': MagicMock,
        }


class MockNodeInstancesClient(BaseMockClient):
    pass


class MockEventsClient(BaseMockClient):

    list_events = []
    count = -1

    def _set(self, list_events, full_count=True):
        self.list_events = list_events
        if full_count:
            self.count = len(self.list_events)

    def get(self, *args, **_):
        return self.list_events, self.count


class MockCloudifyRestClient(object):

    def __init__(self):
        self.blueprints = MockBlueprintsClient()
        self.deployments = MockDeploymentsClient()
        self.executions = MockExecutionsClient()
        self.node_instances = MockNodeInstancesClient()
        self.events = MockEventsClient()
        self.secrets = MagicMock()
        self.plugins = MagicMock()

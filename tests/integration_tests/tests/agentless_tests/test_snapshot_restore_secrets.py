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

from integration_tests.framework.utils import create_rest_client

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    upload_and_restore_snapshot,
    get_resource,
)


class TestSnapshotSecrets(AgentlessTestCase):
    maxDiff = None
    run_storage_reset = False

    def test_restore_3_4_2_secrets(self):
        with open(get_resource('secrets_restores/3.4.2-key1')) as key_handle:
            key1 = key_handle.read()

        with open(get_resource('secrets_restores/3.4.2-key2')) as key_handle:
            key2 = key_handle.read()

        self._test_restore_secrets('secretshot_3.4.2.zip', key1, key2,
                                   tenant='restore_tenant')

    def test_restore_4_0_0_secrets(self):
        with open(get_resource('secrets_restores/4.0.0-key1')) as key_handle:
            key1 = key_handle.read()

        with open(get_resource('secrets_restores/4.0.0-key2')) as key_handle:
            key2 = key_handle.read()

        self._test_restore_secrets('secretshot_4.0.zip', key1, key2)

    def test_restore_4_0_1_secrets(self):
        with open(get_resource('secrets_restores/4.0.1-key1')) as key_handle:
            key1 = key_handle.read()

        with open(get_resource('secrets_restores/4.0.1-key2')) as key_handle:
            key2 = key_handle.read()

        self._test_restore_secrets('secretshot_4.0.1.zip', key1, key2)

    def _test_restore_secrets(self, snapshot, key1, key2, tenant=None):
        upload_and_restore_snapshot(snapshot, 'snapshot_abc123', tenant)
        # Set tenant to default tenant after restore to check with correct
        # tenant name. Setting it before the restore will cause the restore
        # to fail.
        self.client = create_rest_client(tenant=tenant or 'default_tenant')

        correct_data = {
            'vm1': {
                'agent': {
                    'get_secret': 'cfyagent_key___etc_cloudify_id_rsa',
                },
            },
            'vm2': {
                'agent': {
                    'get_secret': 'cfyagent_key___etc_cloudify_something.pem',
                },
            },
            'some_sort_of_thing': {
                'runtime_properties': {
                     'prop1': '/etc/cloudify/id_rsa',
                     'prop2': '/etc/cloudify/something.pem',
                     'prop3': '/etc/cloudify/agent_key.pem',
                },
                'node_properties': {
                    'notkey': '/etc/cloudify/agent_key.pem',
                    'something': {
                        'get_secret': 'cfyagent_key___etc_cloudify_id_rsa',
                    },
                },
                'start_operation_inputs': {
                    'an_input': {
                        'get_secret': 'cfyagent_key___etc_cloudify_id_rsa',
                    },
                    'fabric_env': {'key_path': '/etc/cloudify/something.pem'},
                    'not_a_key': '/etc/cloudify/agent_key.pem',
                    'otherput': {
                        'get_secret': (
                            'cfyagent_key___etc_cloudify_something.pem'
                        ),
                    },
                    'script_path': 'scripts/something.sh',
                },
            },
            'secrets': {
                'cfyagent_key___etc_cloudify_something.pem': key1,
                'cfyagent_key___etc_cloudify_id_rsa': key2,
            },
        }

        found = {
            'vm1': False,
            'vm2': False,
            'some_sort_of_thing': False,
        }

        nodes_and_instances = []
        nodes_and_instances.extend(self.client.node_instances.list())
        nodes_and_instances.extend(self.client.nodes.list())
        for node in nodes_and_instances:
            if 'node_id' in node:
                node_id = node['node_id']
                props = node['runtime_properties']
                instance = True
            else:
                node_id = node['id']
                props = node['properties']
                instance = False

            if node_id in ('vm1', 'vm2'):
                found[node_id] = True
                self.assertEquals(
                    props['cloudify_agent']['key'],
                    correct_data[node_id]['agent'],
                )

            elif node_id == 'some_sort_of_thing':
                found[node_id] = True
                if instance:
                    self.assertEquals(
                        props,
                        correct_data[node_id]['runtime_properties'],
                    )
                else:
                    self.assertEquals(
                        props,
                        correct_data[node_id]['node_properties'],
                    )

                    operations = node['operations']
                    start_op = operations[
                        'cloudify.interfaces.lifecycle.start']
                    self.assertEquals(
                        start_op['inputs'],
                        correct_data[node_id]['start_operation_inputs'],
                    )

        self.assertEquals(
            found,
            {key: True for key in found.keys()}
        )

        secrets = self.client.secrets.list()

        secrets = {
            secret['key']: self.client.secrets.get(secret['key'])['value']
            for secret in secrets
        }
        self.assertEquals(
            secrets,
            correct_data['secrets'],
        )

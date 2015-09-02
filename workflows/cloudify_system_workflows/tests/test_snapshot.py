import unittest

from cloudify_rest_client.node_instances import NodeInstance

from cloudify_system_workflows.snapshot import insert_agents_data


class SnapshotTest(unittest.TestCase):

    def test_insert_agents_data(self):
        agents = {
            'nc1': {
                'host': {
                    'host_55e78': {
                        'queue': 'host_55e78',
                        'ip': '10.0.4.12',
                        'user': 'vagrant',
                        'name': 'host_55e78'
                    }
                }
            },
            'nc2': {
                'host': {
                    'host_4440c': {
                        'queue': 'host_4440c',
                        'ip': '10.0.4.92',
                        'user': 'vagrant',
                        'name': 'host_4440c'
                    }
                }
            }
        }

        instances = {
            'host_4440c': {},
            'host_55e78': {
                'prop': 'value'
            },
            'node_123ea': {
                'prop': 'value node'
            }
        }

        updates = {}

        class NodeInstancesClient(object):
            def get(self, node_instance_id):
                return NodeInstance({
                    'runtime_properties': instances[node_instance_id]
                })

            def update(self, node_instance_id, runtime_properties):
                updates[node_instance_id] = runtime_properties

        class RestClient(object):
            @property
            def node_instances(self):
                return NodeInstancesClient()

        insert_agents_data(RestClient(), agents)
        expected_updates = {
            'host_4440c': {
                'cloudify_agent': {
                    'queue': 'host_4440c',
                    'ip': '10.0.4.92',
                    'user': 'vagrant',
                    'name': 'host_4440c'
                }
            },
            'host_55e78': {
                'prop': 'value',
                'cloudify_agent': {
                    'queue': 'host_55e78',
                    'ip': '10.0.4.12',
                    'user': 'vagrant',
                    'name': 'host_55e78'
                }
            },
        }
        self.assertEquals(updates, expected_updates)

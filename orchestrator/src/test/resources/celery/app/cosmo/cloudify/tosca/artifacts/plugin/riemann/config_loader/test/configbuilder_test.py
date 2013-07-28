import unittest
from configbuilder import build_riemann_config

class TestConfigBuilder(unittest.TestCase):

    def setUp(self):
        with open('../../../../../../../../../org/cloudifysource/cosmo/orchestrator/integration/config/riemann.config.template', 'r') as f:
            self.template = f.read()
        self.policies = {
            'node1': {
                'start_detection_policy': {
                    'on_event': {
                        'reachable': 'true',
                        'ip': '10.0.0.5'
                    },
                    'rules': {
                        'rule1': {
                            'type': 'status_equals',
                            'properties': {
                                'service': 'vagrant machine status',
                                'state': 'running'
                            }
                        },
                        'rule2': {
                            'type': 'metric_equals',
                            'properties': {
                                'service': 'vagrant machine status',
                                'metric': '100.0'
                            }
                        },
                    }
                },
                'failure_detection_policy': {
                    'on_event': {
                        'reachable': 'false',
                        'ip': '10.0.0.5'
                    },
                    'rules': {
                        'rule1': {
                            'type': 'status_not_equals',
                            'properties': {
                                'service': 'vagrant machine status',
                                'state': 'running'
                            }
                        },
                    }
                },
            },
            'node2': {
                'start_detection_policy': {
                    'on_event': {
                        'reachable': 'true',
                        'ip': '10.0.0.5'
                    },
                    'rules': {
                        'rule1': {
                            'type': 'status_equals',
                            'properties': {
                                'service': 'vagrant machine status',
                                'state': 'running'
                            }
                        },
                    }
                },
            }
        }
        self.rules = {
            'status_equals': '''
                (service "${service}")
                (state "${state}")
            ''',
            'status_not_equals': '''
                (service "${service}")
                (not (state "${state}"))
            ''',
            'metric_equals': '''
                (service "${service}")
                (metric ${metric})
            ''',
            'metric_not_equals': '''
                (service "${service}")
                (not (metric ${metric}))
            '''
        }


    def test_build_riemann_config(self):
        print build_riemann_config(self.template, self.policies, self.rules)

if __name__ == '__main__':
    unittest.main()

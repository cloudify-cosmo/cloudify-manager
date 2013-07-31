import unittest
from configbuilder import build_riemann_config

class TestConfigBuilder(unittest.TestCase):

    def setUp(self):
        with open('../../../../../../../../../riemann/riemann.config.template', 'r') as f:
            self.template = f.read()
        self.policies = {
            'node1': {
                'start_detection_policy': {
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
        self.policies_events = {
            'start_detection_policy': '''
                (fn [event]
                    (let [ip-event (assoc event :host "$node_id"
                                                :service "ip"
                                                :state (get event :host)
                                                :description "$event"
                                                :tags ["cosmo"])]
                        (call-rescue ip-event [index prn]))
                    (let [reachable-event (assoc event :host "$node_id"
                                                       :service "reachable"
                                                       :state "true"
                                                       :description "$event"
                                                       :tags ["cosmo"])]
                        (call-rescue reachable-event [index prn])))
            ''',
            'failure_detection_policy':'''
                (fn [event]
                    (let [ip-event (assoc event :host "$node_id"
                                                :service "ip"
                                                :state (get event :host)
                                                :description "$event"
                                                :tags ["cosmo"])]
                        (call-rescue ip-event [index prn]))
                    (let [reachable-event (assoc event :host "$node_id"
                                                       :service "reachable"
                                                       :state "true"
                                                       :description "$event"
                                                       :tags ["cosmo"])]
                        (call-rescue reachable-event [index prn])))
            '''
        }


    def test_build_riemann_config(self):
        print build_riemann_config(self.template, self.policies, self.rules, self.policies_events)

if __name__ == '__main__':
    unittest.main()

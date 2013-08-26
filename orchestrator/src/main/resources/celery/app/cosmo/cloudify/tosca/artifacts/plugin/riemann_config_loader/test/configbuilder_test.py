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
                        }
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
            },
            'node3': {
                'performance_policy': {
                    'rules': {
                        'rule1': {
                            'type': 'metric_below',
                            'properties': {
                                'service': 'vagrant machine status',
                                'metric': '10'
                            }
                        },
                    }
                },
            }
        }
        self.rules = {
            'status_equals': '''
                (changed-state
                    (where
                        (and
                            (service "${service}")
                            (state "${state}")
                            (tagged "name=$node_id"))
                        $node_policy_events)
                )
            ''',
            'status_not_equals': '''
                (changed-state
                    (where
                        (and
                            (service "${service}")
                            (not (state "${state}"))
                            (tagged "name=$node_id"))
                        $node_policy_events)
                )
            ''',
            'metric_below': '''
                (by [:host :service] (changed (fn [e] (> ${metric} (:metric e))) {:init false}
                    (where
                        (and
                            (service "${service}")
                            (> (${metric} metric))
                            (tagged "name=$node_id"))
                        $node_policy_events)
                ))
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
            ''',
            'performance_policy':'''
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

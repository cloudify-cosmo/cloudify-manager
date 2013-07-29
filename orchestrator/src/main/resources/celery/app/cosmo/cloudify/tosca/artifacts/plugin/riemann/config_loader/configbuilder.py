__author__ = 'dank'

import string
import sys

def build_riemann_config(template, policies, rules):
    
    policies_config = []

    for node_id, node_policies in policies.items():
        for node_policy in node_policies.values():
            node_policy = build_node_policy_config(node_id, node_policy, rules)
            policies_config.append(node_policy)

    return string.Template(template).substitute(dict(
        events_mapping= ''.join(policies_config)
    ))


def build_node_policy_config(node_id, node_policy, rules):

    policy_config_template = '''
        (where 
            (and
                $node_policy_rules
                (tagged_with_name event "$node_id"))
            $node_policy_events)
    '''
    
    node_policy_rules = []
    for rule in node_policy['rules'].values():
        rule_template = rules[rule['type']]
        rule_properties = rule['properties']
        rule_config = build_node_policy_rule_config(rule_template, rule_properties)
        node_policy_rules.append(rule_config)

    node_policy_on_event = node_policy['on_event']
    node_policy_events = "(create_events %(clojure_on_event)s index)" % dict(
        clojure_on_event = to_clojure_map(node_policy_on_event)
    )

    return string.Template(policy_config_template).substitute(dict(
        node_id = node_id,
        node_policy_rules = ''.join(node_policy_rules),
        node_policy_events = node_policy_events
    ))


def build_node_policy_rule_config(rule_template, properties):
    return string.Template(rule_template).substitute(properties)


def to_clojure_map(py_map):
    entries = []
    for key, value in py_map.items():
        entries.append('"%(key)s" "%(value)s"' % dict(key=key, value=value))
    return '{%(entries)s}' % dict(entries=' '.join(entries))

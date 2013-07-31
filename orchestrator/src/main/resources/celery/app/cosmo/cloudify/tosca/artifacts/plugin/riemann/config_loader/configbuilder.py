__author__ = 'dank'

import string
import sys
import json

def build_riemann_config(template, policies, rules, policies_events):
    
    policies_config = []

    for node_id, node_policies in policies.items():
        for node_policy_name, node_policy in node_policies.items():
            node_policy_events_template = policies_events[node_policy_name]
            node_policy = build_node_policy_config(node_id,
                                                   node_policy,
                                                   rules,
                                                   node_policy_events_template,
                                                   node_policy_name)
            policies_config.append(node_policy)

    return string.Template(template).substitute(dict(
        events_mapping = ''.join(policies_config)
    ))


def build_node_policy_config(node_id,
                             node_policy,
                             rules,
                             node_policy_events_template,
                             node_policy_name):

    policy_config_template = '''
        (where 
            (and
                $node_policy_rules
                (tagged "name=$node_id"))
            $node_policy_events)
    '''
    
    node_policy_rules = []
    for rule in node_policy['rules'].values():
        rule_template = rules[rule['type']]
        rule_properties = rule['properties']
        rule_config = build_node_policy_rule_config(rule_template, rule_properties)
        node_policy_rules.append(rule_config)

    event_json = build_node_policy_event(
        node_id,
        node_policy_name,
        node_policy['rules'])
    node_policy_events = string.Template(node_policy_events_template).substitute(dict(
        event = event_json,
        node_id = node_id
    ))

    return string.Template(policy_config_template).substitute(dict(
        node_id = node_id,
        node_policy_rules = ''.join(node_policy_rules),
        node_policy_events = node_policy_events
    ))


def build_node_policy_event(node_id, node_policy_name, node_policy_rules):
    event = {}
    event['app_id'] = node_id.split('.')[0]
    event['node_id'] = node_id
    event['policy'] = node_policy_name
    event['rule'] = node_policy_rules
    return json.dumps(event).replace('"','\\"')


def build_node_policy_rule_config(rule_template, properties):
    return string.Template(rule_template).substitute(properties)

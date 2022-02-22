from manager_rest.storage.models import Deployment, DeploymentsFilter
from manager_rest.rest.filters_utils import (get_filter_rules_from_filter_id,
                                             create_filter_rules_list,
                                             FilterRule)


def get_filter_rules(raw_filter_rules,
                     resource_model,
                     filters_model,
                     filter_id):
    filter_rules = create_filter_rules_list(raw_filter_rules, resource_model)
    if filter_id:
        existing_filter_rules = get_filter_rules_from_filter_id(
            filter_id, filters_model)
        for existing_filter_rule in existing_filter_rules:
            filter_rule_elem = FilterRule(existing_filter_rule['key'],
                                          existing_filter_rule['values'],
                                          existing_filter_rule['operator'],
                                          existing_filter_rule['type'])
            if filter_rule_elem in filter_rules:
                continue
            filter_rules.append(filter_rule_elem)

    return filter_rules


def get_deployments_with_sm(sm,
                            deployment_id,
                            filter_id=None,
                            labels=None,
                            tenants=None,
                            display_name_specs=None):
    filter_rules = []
    if labels:
        filter_rules.extend(
            {"key": list(label.keys())[0],
             "values": [str(list(label.values())[0])],
             "operator": "any_of",
             "type": "label"}
            for label in labels
        )
    if tenants:
        filter_rules.append(
            {"key": "tenant_name",
             "values": [str(t) for t in tenants],
             "operator": "any_of",
             "type": "attribute"}
        )
    if display_name_specs:
        for op, spec in display_name_specs.items():
            filter_rules.append(
                {"key": "display_name",
                 "values": [str(spec)],
                 "operator": "any_of" if op == "equals_to" else op,
                 "type": "attribute"})

    filter_rules = get_filter_rules(filter_rules,
                                    Deployment,
                                    DeploymentsFilter,
                                    filter_id)

    result = sm.list(
        Deployment,
        include=['id'],
        filters={'id': str(deployment_id)},
        get_all_results=True,
        filter_rules=filter_rules
    )

    return result

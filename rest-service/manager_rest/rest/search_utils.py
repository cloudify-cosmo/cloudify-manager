from manager_rest.storage.models import (Blueprint, BlueprintsFilter,
                                         Deployment, DeploymentsFilter)
from manager_rest.rest.filters_utils import (get_filter_rules_from_filter_id,
                                             create_filter_rules_list,
                                             FilterRule)


class GetEntitiesWithStorageManager:
    def __init__(self, sm):
        self.sm = sm

    def get(self, data_type, entity_id, **kwargs):
        if data_type == 'blueprint_id':
            return self.get_blueprints(entity_id, **kwargs)
        elif data_type == 'deployment_id':
            return self.get_deployments(entity_id, **kwargs)
        elif data_type == 'capability_value':
            return self.get_capability_value(entity_id, **kwargs)
        raise NotImplementedError("Getter function not defined for "
                                  f"data type '{data_type}'")

    def get_deployments(self, deployment_id,
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

        return self.sm.list(
            Deployment,
            include=['id'],
            filters={'id': str(deployment_id)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_blueprints(self, blueprint_id,
                       filter_id=None,
                       labels=None,
                       tenants=None,
                       id_specs=None):
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
        if id_specs:
            for op, spec in id_specs.items():
                filter_rules.append(
                    {"key": "id",
                     "values": [str(spec)],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})

        filter_rules = get_filter_rules(filter_rules,
                                        Blueprint,
                                        BlueprintsFilter,
                                        filter_id)

        return self.sm.list(
            Blueprint,
            include=['id'],
            filters={'id': str(blueprint_id)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_capability_value(self, id, **kwargs):
        raise NotImplementedError('get_capability_value not implemented')


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

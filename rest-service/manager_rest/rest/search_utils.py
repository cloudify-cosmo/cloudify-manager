from collections import defaultdict

from dsl_parser.functions import is_function

from manager_rest.manager_exceptions import BadParametersError
from manager_rest.storage.models import (Blueprint, BlueprintsFilter,
                                         Deployment, DeploymentsFilter,
                                         Secret, Node)
from manager_rest.rest.filters_utils import (get_filter_rules_from_filter_id,
                                             create_filter_rules_list,
                                             FilterRule)


class GetValuesWithStorageManager:
    def __init__(self, sm):
        self.sm = sm

    def get(self, data_type, value, **kwargs):
        if data_type == 'blueprint_id':
            return {b.id for b in self.get_blueprints(value, **kwargs)}
        elif data_type == 'deployment_id':
            return {d.id for d in self.get_deployments(value, **kwargs)}
        elif data_type == 'secret_key':
            return {s.key for s in self.get_secrets(value, **kwargs)}
        elif data_type == 'capability_value':
            return {cap_details['value']
                    for dep_cap in self.get_capability_values(value, **kwargs)
                    for cap in dep_cap['capabilities']
                    for cap_details in cap.values()}
        elif data_type == 'node_id':
            return {n.id for n in self.get_nodes(value, **kwargs)}
        elif data_type == 'node_type':
            return {n.type for n in self.get_node_types(value, **kwargs)}
        raise NotImplementedError("Getter function not defined for "
                                  f"data type '{data_type}'")

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

        filter_rules = get_filter_rules(Blueprint, 'id', BlueprintsFilter,
                                        filter_id, filter_rules, None)

        return self.sm.list(
            Blueprint,
            include=['id'],
            filters={'id': str(blueprint_id)},
            get_all_results=True,
            filter_rules=filter_rules
        )

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

        filter_rules = get_filter_rules(Deployment, 'display_name',
                                        DeploymentsFilter,
                                        filter_id, filter_rules, None)

        return self.sm.list(
            Deployment,
            include=['id'],
            filters={'id': str(deployment_id)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_secrets(self, secret_key,
                    key_specs=None,
                    valid_values=None):
        filter_rules = []
        if key_specs:
            for op, spec in key_specs.items():
                filter_rules.append(
                    {"key": "key",
                     "values": [str(spec)],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})
        if valid_values:
            filter_rules.append(
                {"key": "key",
                 "values": [str(v) for v in valid_values],
                 "operator": "any_of",
                 "type": "attribute"})

        filter_rules = get_filter_rules(Secret, 'key', None, None,
                                        filter_rules, None)

        return self.sm.list(
            Secret,
            include=['key'],
            filters={'key': str(secret_key)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_capability_values(self, capability_value,
                              deployment_id=None,
                              valid_values=None,
                              capability_key_specs=None):
        if not deployment_id:
            raise BadParametersError(
                "You should provide 'deployment_id' when getting capability "
                "values.  Make sure you have `deployment_id` constraint "
                "declared for your 'capability_value' parameter.")
        deployments = self.sm.list(
            Deployment,
            include=['id', 'capabilities'],
            filters={'id': str(deployment_id)},
            get_all_results=True,
        )
        dep_capabilities = defaultdict(lambda: [])
        for dep in deployments:
            if not dep.capabilities:
                continue
            for key, capability in dep.capabilities.items():
                if is_function(capability.get('value')):
                    continue
                if capability_matches(key, capability, capability_value,
                                      valid_values, capability_key_specs):
                    dep_capabilities[dep.id].append({key: capability})
        return [{'deployment_id': k, 'capabilities': v}
                for k, v in dep_capabilities.items()]

    def get_nodes(self, node_id,
                  deployment_id=None,
                  id_specs=None,
                  valid_values=None):
        if not deployment_id:
            raise BadParametersError(
                "You should provide 'deployment_id' when getting node id-s. "
                "Make sure you have `deployment_id` constraint declared for "
                "your 'node_id' parameter.")
        filter_rules = []
        if id_specs:
            for op, spec in id_specs.items():
                filter_rules.append(
                    {"key": "id",
                     "values": [str(spec)],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})
        if valid_values:
            filter_rules.append(
                {"key": "id",
                 "values": [str(v) for v in valid_values],
                 "operator": "any_of",
                 "type": "attribute"})

        filter_rules = get_filter_rules(Node, 'id', None, None,
                                        filter_rules, None)

        return self.sm.list(
            Node,
            include=['id'],
            filters={'deployment_id': str(deployment_id),
                     'id': str(node_id)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_node_types(self, node_type,
                       deployment_id=None,
                       type_specs=None,
                       valid_values=None):
        if not deployment_id:
            raise BadParametersError(
                "You should provide 'deployment_id' when getting node "
                "templates.  Make sure you have `deployment_id` constraint "
                "declared for your 'node_id' parameter.")
        filter_rules = []
        if type_specs:
            for op, spec in type_specs.items():
                filter_rules.append(
                    {"key": "type",
                     "values": [str(spec)],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})
        if valid_values:
            filter_rules.append(
                {"key": "type",
                 "values": [str(v) for v in valid_values],
                 "operator": "any_of",
                 "type": "attribute"})

        filter_rules = get_filter_rules(Node, 'type', None, None,
                                        filter_rules, None)

        return self.sm.list(
            Node,
            include=['type'],
            filters={'deployment_id': str(deployment_id),
                     'type': str(node_type)},
            get_all_results=True,
            filter_rules=filter_rules
        )


def capability_matches(capability_key, capability, search_value,
                       valid_values=None,
                       capability_key_specs=None):
    if capability_key_specs:
        for operator, value in capability_key_specs.items():
            if operator == 'contains':
                if value not in capability_key:
                    return False
            elif operator == 'starts_with':
                if not capability_key.startswith(str(value)):
                    return False
            elif operator == 'ends_with':
                if not capability_key.endswith(str(value)):
                    return False
            elif operator == 'equals_to':
                if capability_key != value:
                    return False
            else:
                raise NotImplementedError(
                    f'Unknown capabilities name pattern operator: {operator}')
        if valid_values:
            if capability['value'] not in valid_values:
                return False

    if search_value:
        return capability['value'] == search_value

    return True


def get_filter_rules(resource_model,
                     resource_field,
                     filters_model,
                     raw_filter_id,
                     raw_filter_rules,
                     dsl_constraints):
    raw_filter = raw_filter_rules or raw_filter_id
    if raw_filter and not dsl_constraints:
        filter_rules = create_filter_rules_list(raw_filter_rules,
                                                resource_model)
        filter_id = raw_filter_id
    elif not raw_filter and dsl_constraints:
        constraints_for_model(resource_field, dsl_constraints)
        filter_id, filter_rules = parse_constraints(dsl_constraints)
    elif not raw_filter and not dsl_constraints:
        return []
    else:
        raise BadParametersError(
            "You should provide either filter_id/filter_rules "
            "or DSL constraints, not both")

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


def constraints_for_model(resource_field, dsl_constraints):
    if 'name_pattern' in dsl_constraints:
        dsl_constraints[f'{resource_field}_specs'] = \
            dsl_constraints.pop('name_pattern')
    if 'valid_values' in dsl_constraints:
        dsl_constraints[f'valid_{resource_field}_values'] = \
            dsl_constraints.pop('valid_values')
    return dsl_constraints


def parse_constraints(dsl_constraints):
    filter_id = dsl_constraints.get('filter_id')
    filter_rules = []
    labels = dsl_constraints.get('labels')
    if labels:
        filter_rules.extend(
            {"key": list(label.keys())[0],
             "values": [list(label.values())[0]],
             "operator": "any_of",
             "type": "label"}
            for label in labels
        )
    tenants = dsl_constraints.get('tenants')
    if tenants:
        filter_rules.append(
            {"key": "tenant_name",
             "values": tenants,
             "operator": "any_of",
             "type": "attribute"}
        )
    valid_id_values = dsl_constraints.get('valid_id_values')
    if valid_id_values:
        filter_rules.append(
            {"key": "id",
             "values": valid_id_values,
             "operator": "any_of",
             "type": "attribute"})
    valid_key_values = dsl_constraints.get('valid_key_values')
    if valid_key_values:
        filter_rules.append(
            {"key": "key",
             "values": valid_key_values,
             "operator": "any_of",
             "type": "attribute"})
    valid_type_values = dsl_constraints.get('valid_type_values')
    if valid_type_values:
        filter_rules.append(
            {"key": "type",
             "values": valid_type_values,
             "operator": "any_of",
             "type": "attribute"})
    display_name_specs = dsl_constraints.get('display_name_specs')
    if display_name_specs:
        for op, spec in display_name_specs.items():
            filter_rules.append(
                {"key": "display_name",
                 "values": [spec],
                 "operator": "any_of" if op == "equals_to" else op,
                 "type": "attribute"})
    id_specs = dsl_constraints.get('id_specs')
    if id_specs:
        for op, spec in id_specs.items():
            filter_rules.append(
                {"key": "id",
                 "values": [spec],
                 "operator": "any_of" if op == "equals_to" else op,
                 "type": "attribute"})
    key_specs = dsl_constraints.get('key_specs')
    if key_specs:
        for op, spec in key_specs.items():
            filter_rules.append(
                {"key": "key",
                 "values": [spec],
                 "operator": "any_of" if op == "equals_to" else op,
                 "type": "attribute"})
    type_specs = dsl_constraints.get('type_specs')
    if type_specs:
        for op, spec in type_specs.items():
            filter_rules.append(
                {"key": "type",
                 "values": [spec],
                 "operator": "any_of" if op == "equals_to" else op,
                 "type": "attribute"})

    return filter_id, filter_rules

from collections import defaultdict
from copy import copy
from typing import List, Dict, Any

from dsl_parser.constants import TYPES_WHICH_REQUIRE_DEPLOYMENT_ID_CONSTRAINT
from dsl_parser.utils import get_function

from manager_rest.manager_exceptions import BadParametersError
from manager_rest.storage.models import (Blueprint, BlueprintsFilter,
                                         Deployment, DeploymentsFilter,
                                         Secret, Node, NodeInstance)
from manager_rest.rest.filters_utils import (get_filter_rules_from_filter_id,
                                             create_filter_rules_list,
                                             FilterRule)
from manager_rest.dsl_functions import evaluate_intrinsic_functions


class GetValuesWithStorageManager:
    def __init__(self, sm, current_deployment_id):
        self.sm = sm
        self.current_deployment_id = current_deployment_id

    def has_deployment_id(self):
        return bool(self.current_deployment_id)

    def get(self, data_type, value, **kwargs):
        params = self.update_deployment_id_constraint(data_type, **kwargs)
        if data_type == 'blueprint_id':
            return {b.id for b in self.get_blueprints(value, **params)}
        elif data_type == 'deployment_id':
            return {d.id for d in self.get_deployments(value, **params)}
        elif data_type == 'secret_key':
            return {s.key for s in self.get_secrets(value, **params)}
        elif data_type == 'capability_value':
            return {cap_details['value']
                    for dep_cap in self.get_capability_values(value, **params)
                    for cap in dep_cap['capabilities']
                    for cap_details in cap.values()}
        elif data_type == 'scaling_group':
            return {sg['name']
                    for sg in self.get_scaling_groups(value, **params)}
        elif data_type == 'node_id':
            return {n.id for n in self.get_nodes(value, **params)}
        elif data_type == 'node_type':
            return {n.type for n in self.get_node_types(value, **params)}
        elif data_type == 'node_instance':
            return {n.id for n in self.get_node_instances(value, **params)}
        elif data_type == 'operation_name':
            return set(self.get_operation_names(value, **params))
        raise NotImplementedError("Getter function not defined for "
                                  f"data type '{data_type}'")

    def get_blueprints(self, blueprint_id,
                       filter_id=None,
                       labels=None,
                       tenants=None,
                       id_specs=None):
        filter_rules: List[Dict[str, Any]] = []
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

        filter_rules = get_filter_rules(
            self.sm, Blueprint, 'id', BlueprintsFilter, filter_id,
            filter_rules, None)

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
        filter_rules: List[Dict[str, Any]] = []
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

        filter_rules = get_filter_rules(
            self.sm, Deployment, 'display_name', DeploymentsFilter, filter_id,
            filter_rules, None)

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

        filter_rules = get_filter_rules(
            self.sm, Secret, 'key', None, None, filter_rules, None)

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
                "Parameters of type 'capability_value' require the "
                f"'deployment_id' constraint ({capability_value}).")
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
            for key, raw_capability in dep.capabilities.items():
                if get_function(raw_capability.get('value')):
                    capability = evaluate_intrinsic_functions(
                        raw_capability, dep.id)
                else:
                    capability = raw_capability
                if capability_matches(key, capability, capability_value,
                                      valid_values, capability_key_specs):
                    dep_capabilities[dep.id].append({key: capability})
        return [{'deployment_id': k, 'capabilities': v}
                for k, v in dep_capabilities.items()]

    def get_scaling_groups(self, scaling_group_name,
                           deployment_id=None,
                           valid_values=None,
                           scaling_group_name_specs=None):
        if not deployment_id:
            raise BadParametersError(
                "Parameters of type 'scaling_group' require the "
                f"'deployment_id' constraint ({scaling_group_name}).")
        deployments = self.sm.list(
            Deployment,
            include=['id', 'scaling_group'],
            filters={'id': str(deployment_id)},
            get_all_results=True,
        )

        results = []
        for dep in deployments:
            if not dep.scaling_groups:
                continue
            for name, scaling_group in dep.scaling_groups.items():
                if scaling_group_name_matches(
                    name,
                    scaling_group_name,
                    valid_values=valid_values,
                    scaling_group_name_specs=scaling_group_name_specs
                ):
                    results.append({
                        'deployment_id': dep.id,
                        'name': name,
                        'members': scaling_group.get('members'),
                        'properties': scaling_group.get('properties'),
                    })

        return results

    def get_nodes(self, node_id,
                  deployment_id=None,
                  id_specs=None,
                  valid_values=None):
        if not deployment_id:
            raise BadParametersError(
                "Parameters of type 'node_id' require the "
                f"'deployment_id' constraint ({node_id}).")
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

        filter_rules = get_filter_rules(
            self.sm, Node, 'id', None, None, filter_rules, None)

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
                "Parameters of type 'node_type' require the "
                f"'deployment_id' constraint ({node_type}).")
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

        filter_rules = get_filter_rules(
            self.sm, Node, 'type', None, None, filter_rules, None)

        return self.sm.list(
            Node,
            include=['type'],
            filters={'deployment_id': str(deployment_id),
                     'type': str(node_type)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_node_instances(self, node_instance,
                           deployment_id=None,
                           id_specs=None,
                           valid_values=None):
        if not deployment_id:
            raise BadParametersError(
                "Parameters of type 'node_instance' require the "
                f"'deployment_id' constraint ({node_instance}).")
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

        filter_rules = get_filter_rules(
            self.sm, NodeInstance, 'id', None, None, filter_rules, None)

        return self.sm.list(
            NodeInstance,
            include=['id'],
            filters={'deployment_id': str(deployment_id),
                     'id': str(node_instance)},
            get_all_results=True,
            filter_rules=filter_rules
        )

    def get_operation_names(self, operation_name,
                            deployment_id=None,
                            valid_values=None,
                            operation_name_specs=None):
        if not deployment_id:
            raise BadParametersError(
                "Parameters of type 'operation_name' require the "
                f"'deployment_id' constraint ({operation_name}).")

        filter_rules = []
        if operation_name_specs:
            for op, spec in operation_name_specs.items():
                filter_rules.append(
                    {"key": "operation_name",
                     "values": [str(spec)],
                     "operator": "any_of" if op == "equals_to" else op,
                     "type": "attribute"})
        if valid_values:
            filter_rules.append(
                {"key": "operation_name",
                 "values": [str(v) for v in valid_values],
                 "operator": "any_of",
                 "type": "attribute"})

        filter_rules = get_filter_rules(
            self.sm, Node, 'operation_name', None, None, filter_rules, None)

        nodes = self.sm.list(
            Node,
            include=['operations'],
            filters={'deployment_id': str(deployment_id)},
            filter_rules=filter_rules,
            get_all_results=True,
        )

        results = []
        for node in nodes:
            if not node.operations:
                continue
            for name, operation_specs in node.operations.items():
                if operation_name_matches(
                    name,
                    operation_name,
                    valid_values=valid_values,
                    operation_name_specs=operation_name_specs,
                ):
                    results.append(name)

        return results

    def update_deployment_id_constraint(self, data_type, **kwargs):
        if data_type not in TYPES_WHICH_REQUIRE_DEPLOYMENT_ID_CONSTRAINT:
            return kwargs
        params = copy(kwargs)
        if 'deployment_id' not in kwargs:
            params['deployment_id'] = self.current_deployment_id
        return params


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


def scaling_group_name_matches(scaling_group_name, search_value,
                               valid_values=None,
                               scaling_group_name_specs=None):
    if scaling_group_name_specs:
        for operator, value in scaling_group_name_specs.items():
            if operator == 'contains':
                if value not in scaling_group_name:
                    return False
            elif operator == 'starts_with':
                if not scaling_group_name.startswith(str(value)):
                    return False
            elif operator == 'ends_with':
                if not scaling_group_name.endswith(str(value)):
                    return False
            elif operator == 'equals_to':
                if scaling_group_name != str(value):
                    return False
            else:
                raise NotImplementedError('Unknown scaling group name '
                                          f'pattern operator: {operator}')
    if valid_values:
        if scaling_group_name not in valid_values:
            return False
    if search_value:
        return scaling_group_name == search_value

    return True


def operation_name_matches(operation_name, search_value,
                           valid_values=None,
                           operation_name_specs=None):
    """Verify if operation_name matches the constraints.

    :param operation_name: name of an operation to test.
    :param search_value: value of an input/parameter of type operation_name,
                         if provided, must exactly match `operation_name`.
    :param valid_values: a list of allowed values for the `operation_name`.
    :param operation_name_specs: a dictionary describing a name_pattern
                                 constraint for `operation_name`.
    :return: `True` if `operation_name` matches the constraints provided with
             the other three parameters.
    """
    if operation_name_specs:
        for operator, value in operation_name_specs.items():
            match operator:
                case 'contains':
                    if value not in operation_name:
                        return False
                case 'starts_with':
                    if not operation_name.startswith(str(value)):
                        return False
                case 'ends_with':
                    if not operation_name.endswith(str(value)):
                        return False
                case 'equals_to':
                    if operation_name != str(value):
                        return False
                case _:
                    raise NotImplementedError('Unknown operation name '
                                              f'pattern operator: {operator}')
    if valid_values:
        if operation_name not in valid_values:
            return False
    if search_value:
        return operation_name == search_value

    return True


def get_filter_rules(sm,
                     resource_model,
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
            sm, filter_id, filters_model)
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
    filter_rules: List[Dict[str, Any]] = []
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
    valid_operation_name_values = \
        dsl_constraints.get('valid_operation_name_values')
    if valid_operation_name_values:
        filter_rules.append(
            {"key": "operation_name",
             "values": valid_operation_name_values,
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

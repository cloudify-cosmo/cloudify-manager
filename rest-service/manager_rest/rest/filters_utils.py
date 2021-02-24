from typing import List

from flask import request

from cloudify._compat import text_type

from manager_rest.rest.rest_utils import validate_inputs
from manager_rest.manager_exceptions import BadFilterRule, BadParametersError
from manager_rest.storage import get_storage_manager, models
from manager_rest.constants import (ATTRS_OPERATORS,
                                    FilterRuleType,
                                    LabelsOperator,
                                    LABELS_OPERATORS,
                                    FILTER_RULE_TYPES)


def get_filter_rules(resource_model: models):
    filter_rules = request.args.get('_filter_rules')
    filter_id = request.args.get('_filter_id')

    if not filter_rules and not filter_id:
        return

    if filter_rules and filter_id:
        raise BadParametersError(
            'Filter rules and filter ID cannot be provided together. '
            'Please specify one of them or neither.'
        )

    if filter_rules:
        return parse_filter_rules(filter_rules, resource_model)

    if filter_id:
        validate_inputs({'filter_id': filter_id})
        filter_elem = get_storage_manager().get(models.Filter, filter_id)
        return filter_elem.value


def parse_filter_rules(filter_rules: List[dict], resource_model: models):
    """Validating the filter rules list.

    :param filter_rules: A list of filter rules. A filter rule is a dictionary
           of the following form:
           {
               key: <key>,
               values: [<list of values>],
               operator: <LabelsOperator> or <AttrsOperator>,
               type: <FilterRuleType>
            }
    :param resource_model: models.Deployment or models.Blueprint
    :return: Parsed filter rules list
    """
    parsed_filter_rules = []
    for filter_rule in filter_rules:
        _assert_filter_rule_structure(filter_rule)

        filter_rule_key = filter_rule['key']
        filter_rule_values = filter_rule['values']
        filter_rule_type = filter_rule['type']
        filter_rule_operator = filter_rule['operator']

        if not isinstance(filter_rule_key, text_type):
            raise BadFilterRule(filter_rule,
                                'The filter rule key must be of type string')
        if not isinstance(filter_rule_values, list):
            raise BadFilterRule(filter_rule,
                                'The filter rule values must be of type list')

        if filter_rule_type == FilterRuleType.LABEL:
            null_operators = [LabelsOperator.IS_NULL,
                              LabelsOperator.IS_NOT_NULL]
            any_of_operators = [LabelsOperator.ANY_OF,
                                LabelsOperator.NOT_ANY_OF]
            if filter_rule_operator not in LABELS_OPERATORS:
                raise BadFilterRule(
                    filter_rule, f"The operator for filtering by labels must "
                                 f"be one of {', '.join(LABELS_OPERATORS)}")
            if filter_rule_operator in null_operators:
                if len(filter_rule_values) > 0:
                    raise BadFilterRule(
                        filter_rule,
                        f"Values list must be empty if the operator is one of "
                        f"{', '.join(null_operators)}")
            else:
                if len(filter_rule_values) == 0:
                    raise BadFilterRule(
                        filter_rule,
                        f"Values list must include at least one item if the "
                        f"operator is one of {', '.join(any_of_operators)}")

        elif filter_rule_type == FilterRuleType.ATTRIBUTE:
            err_attr_msg = f"Allowed attributes to filter " \
                           f"{resource_model.__tablename__} by are " \
                           f"{','.join(resource_model.allowed_filter_attrs)}"
            if filter_rule_operator not in ATTRS_OPERATORS:
                raise BadFilterRule(
                    filter_rule,
                    f"The operator for filtering by attributes must be one"
                    f" of {', '.join(ATTRS_OPERATORS)}")
            if filter_rule_key not in resource_model.allowed_filter_attrs:
                raise BadFilterRule(filter_rule, err_attr_msg)

        else:
            raise BadFilterRule(filter_rule,
                                f"Filter rule type must be one of "
                                f"{', '.join(FILTER_RULE_TYPES)}")

        value_msg_prefix = (None if len(filter_rule_values) == 1 else
                            'One of the filter rule values')

        parsed_values_list = []
        for value in filter_rule_values:
            try:
                validate_inputs({'filter rule key': filter_rule_key})
                validate_inputs({'filter rule value': value},
                                err_prefix=value_msg_prefix)
            except BadParametersError as e:
                err_msg = f'The filter rule {filter_rule} is invalid. '
                raise BadParametersError(err_msg + str(e))
            parsed_values_list.append(value.lower())

        parsed_filter_rules.append({'key': filter_rule_key.lower(),
                                    'values': parsed_values_list,
                                    'operator': filter_rule_operator,
                                    'type': filter_rule_type})

    return parsed_filter_rules


def _assert_filter_rule_structure(filter_rule):
    if not isinstance(filter_rule, dict):
        raise BadFilterRule(filter_rule, 'The filter rule is not a dictionary')

    if not (all(key in filter_rule for key in
                ['key', 'values', 'operator', 'type'])):
        raise BadFilterRule(
            filter_rule, 'At least one of the entries in the filter rule '
                         'is missing')

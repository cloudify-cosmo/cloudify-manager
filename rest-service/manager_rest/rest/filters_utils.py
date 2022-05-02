from typing import List, Union, NewType

from cloudify._compat import text_type

from manager_rest.storage import models
from manager_rest.rest.rest_utils import validate_inputs, parse_label
from manager_rest.manager_exceptions import BadFilterRule, BadParametersError
from manager_rest.constants import (ATTRS_OPERATORS,
                                    FilterRuleType,
                                    AttrsOperator,
                                    LabelsOperator,
                                    LABELS_OPERATORS,
                                    FILTER_RULE_TYPES)


class FilterRule(dict):
    def __init__(self, key, values, operator, filter_rule_type):
        super().__init__()
        self['key'] = key.lower()
        self['values'] = values
        self['operator'] = operator
        self['type'] = filter_rule_type

    def _key(self):
        return (self['key'], tuple(self['values']),
                self['operator'], self['type'])

    def __hash__(self):
        return hash(self._key())


FilteredModels = NewType('FilteredModels',
                         Union[models.Deployment, models.Blueprint])


def get_filter_rules_from_filter_id(sm, filter_id, filters_model):
    if not filter_id or not filters_model:
        return None

    validate_inputs({'filter_id': filter_id})
    filter_elem = sm.get(filters_model, filter_id)
    return filter_elem.value


def create_filter_rules_list(raw_filter_rules: List[dict],
                             resource_model: FilteredModels):
    """Validate the raw filter rules list and return a FilterRule items list.

    :param raw_filter_rules: A list of filter rules. A filter rule is a
           dictionary of the following form:
           {
               key: <key>,
               values: [<list of values>],
               operator: <LabelsOperator> or <AttrsOperator>,
               type: <FilterRuleType>
            }
    :param resource_model: One of FilteredModels
    :return: A list of FilterRule items
    """
    filter_rules_list = []
    for filter_rule in raw_filter_rules:
        _assert_filter_rule_structure(filter_rule)

        filter_rule_key = filter_rule['key']
        filter_rule_values = filter_rule['values']
        filter_rule_type = filter_rule['type']
        filter_rule_operator = filter_rule['operator']

        if not isinstance(filter_rule_key, text_type):
            raise BadFilterRule(filter_rule,
                                'The filter rule key must be a string')
        if not isinstance(filter_rule_values, list):
            raise BadFilterRule(filter_rule,
                                'The filter rule values must be a list')

        if filter_rule_type == FilterRuleType.LABEL:
            null_operators = [LabelsOperator.IS_NULL,
                              LabelsOperator.IS_NOT_NULL]
            multiple_values_operators = [LabelsOperator.ANY_OF,
                                         LabelsOperator.NOT_ANY_OF,
                                         LabelsOperator.IS_NOT]
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
                        f"operator is one of "
                        f"{', '.join(multiple_values_operators)}")

        elif filter_rule_type == FilterRuleType.ATTRIBUTE:
            err_attr_msg = f"Allowed attributes to filter " \
                           f"{resource_model.__tablename__} by are " \
                           f"{', '.join(resource_model.allowed_filter_attrs)}"
            if filter_rule_operator not in ATTRS_OPERATORS:
                raise BadFilterRule(
                    filter_rule,
                    f"The operator for filtering by attributes must be one"
                    f" of {', '.join(ATTRS_OPERATORS)}")
            if filter_rule_operator == AttrsOperator.IS_NOT_EMPTY:
                if len(filter_rule_values) > 0:
                    raise BadFilterRule(
                        filter_rule,
                        f"Values list must be empty if the operator is "
                        f"{AttrsOperator.IS_NOT_EMPTY}")
            if filter_rule_key not in resource_model.allowed_filter_attrs:
                raise BadFilterRule(filter_rule, err_attr_msg)
            if (filter_rule_key == 'schedules' and
                    filter_rule_operator != AttrsOperator.IS_NOT_EMPTY):
                raise BadFilterRule(
                    filter_rule,
                    f"Filtering by deployment schedules is only possible with "
                    f"the {AttrsOperator.IS_NOT_EMPTY} operator")

        else:
            raise BadFilterRule(filter_rule,
                                f"Filter rule type must be one of "
                                f"{', '.join(FILTER_RULE_TYPES)}")

        for value in filter_rule_values:
            try:
                if filter_rule_type == FilterRuleType.LABEL:
                    parse_label(filter_rule_key, value)
                else:
                    validate_inputs({"attributes' filter rule value": value})
            except BadParametersError as e:
                raise BadFilterRule(filter_rule, str(e))

        new_filter_rule = FilterRule(filter_rule_key,
                                     filter_rule_values,
                                     filter_rule_operator,
                                     filter_rule_type)
        if new_filter_rule in filter_rules_list:
            continue
        filter_rules_list.append(new_filter_rule)

    return filter_rules_list


def _assert_filter_rule_structure(filter_rule):
    if not isinstance(filter_rule, dict):
        raise BadFilterRule(filter_rule, 'The filter rule is not a dictionary')

    if filter_rule.keys() != {'key', 'values', 'operator', 'type'}:
        raise BadFilterRule(
            filter_rule, 'At least one of the entries in the filter rule '
                         'is missing')

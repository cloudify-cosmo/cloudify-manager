import re

from manager_rest import manager_exceptions
from manager_rest.rest.rest_utils import validate_inputs
from manager_rest.constants import (LABEL_LEN, EQUAL, NOT_EQUAL, IS_NULL,
                                    IS_NOT_NULL)


class BadLabelsFilter(manager_exceptions.BadParametersError):
    def __init__(self, labels_filter_value):
        super(BadLabelsFilter, self).__init__(
            'The labels filter `{0}` is not in the right format. It must be '
            'one of: <key>=<value>, <key>=[<value1>,<value2>,...], '
            '<key>!=<value>, <key>!=[<value1>,<value2>,...], <key> is null, '
            '<key> is not null'.format(labels_filter_value)
        )


def create_labels_filters_mapping(labels_filters_list):
    """Validate and parse a list of labels filters

    :param labels_filters_list: A list of labels filters. Labels filters must
           be one of: <key>=<value>, <key>=[<value1>,<value2>,...],
           <key>!=<value>, <key>!=[<value1>,<value2>,...], <key> is null,
           <key> is not null

    :return The labels filters mapping dictionary with the following schema:
            {NOT_EQUAL: {}, EQUAL: {}, IS_NULL: [], IS_NOT_NULL: []}
    """
    labels_filters_mapping = {}
    for labels_filter in labels_filters_list:
        if '!=' in labels_filter:
            label_key, label_values = _parse_labels_filter(labels_filter, '!=')
            # a!=b and a!=c <=> a!=[b, c]
            labels_filters_mapping.setdefault(NOT_EQUAL, {}).setdefault(
                label_key, []).extend(label_values)

        elif '=' in labels_filter:
            label_key, label_values = _parse_labels_filter(labels_filter, '=')
            labels_filters_mapping.setdefault(EQUAL, {})
            if label_key in labels_filters_mapping[EQUAL]:
                raise manager_exceptions.BadParametersError(
                    'You cannot provide two filter rules with equal sign that '
                    'have the same key. E.g. `a=b and a=c` is not allowed.')

            labels_filters_mapping[EQUAL][label_key] = label_values

        elif 'null' in labels_filter:
            match_null = re.match(r'(\S+) is null', labels_filter)
            match_not_null = re.match(r'(\S+) is not null', labels_filter)
            if match_null:
                labels_filters_mapping.setdefault(IS_NULL, []).append(
                    match_null.group(1).lower())
            elif match_not_null:
                labels_filters_mapping.setdefault(IS_NOT_NULL, []).append(
                    match_not_null.group(1).lower())
            else:
                raise BadLabelsFilter(labels_filter)

        else:
            raise BadLabelsFilter(labels_filter)

    return labels_filters_mapping


def _parse_labels_filter(labels_filter, sign):
    """Validate and parse a labels filter

    :param labels_filter: One of <key>=<value>, <key>=[<value1>,<value2>,...],
           <key>!=<value>, <key>!=[<value1>,<value2>,...]
    :param sign: Either '=' or '!='
    :return: The labels_filter, with its key and value(s) in lowercase and
             stripped of whitespaces
    """
    try:
        raw_label_key, raw_label_value = labels_filter.split(sign)
    except ValueError:  # e.g. a=b=c
        raise BadLabelsFilter(labels_filter)

    label_key = raw_label_key.strip().lower()
    label_values = _get_label_value(raw_label_value.strip().lower())
    value_msg_prefix = (None if len(label_values) == 1 else
                        'One of the filter values')

    parsed_label_values_list = []
    for value in label_values:
        try:
            parsed_value = value.strip()
            validate_inputs(
                {'filter key': label_key}, len_input_value=LABEL_LEN)
            validate_inputs(
                {'filter value': parsed_value}, len_input_value=LABEL_LEN,
                err_prefix=value_msg_prefix)
        except manager_exceptions.BadParametersError as e:
            err_msg = 'The filter rule {0} is invalid. '.format(labels_filter)
            raise manager_exceptions.BadParametersError(err_msg + str(e))

        parsed_label_values_list.append(parsed_value)

    return label_key, parsed_label_values_list


def _get_label_value(raw_label_value):
    if raw_label_value.startswith('[') and raw_label_value.endswith(']'):
        return raw_label_value.strip('[]').split(',')

    return [raw_label_value]

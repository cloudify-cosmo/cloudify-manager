import re

from manager_rest import manager_exceptions
from manager_rest.storage.models_base import db


def add_labels_filters_to_query(query, labels_model, labels_filters):
    query = query.join(labels_model)
    for labels_filter in labels_filters:
        try:
            if '!=' in labels_filter:
                label_key, raw_label_value = labels_filter.split('!=')
                label_value = _get_label_value(raw_label_value)
                if isinstance(label_value, list):
                    query = query.filter(key_not_equal_list_values(
                        labels_model, label_key, label_value))
                else:
                    query = query.filter(key_not_equal_value(
                        labels_model, label_key, label_value))

            elif '=' in labels_filter:
                label_key, raw_label_value = labels_filter.split('=')
                label_value = _get_label_value(raw_label_value)
                if isinstance(label_value, list):
                    query = query.filter(key_equal_list_values(
                        labels_model, label_key, label_value))
                else:
                    query = query.filter(
                        key_equal_value(labels_model, label_key, label_value))

            elif 'null' in labels_filter:
                match_null = re.match(r'(\S+) is null', labels_filter)
                match_not_null = re.match(r'(\S+) is not null', labels_filter)
                if match_null:
                    query = query.filter(
                        key_not_exist(labels_model, match_null.group(1)))
                elif match_not_null:
                    query = query.filter(
                        key_exist(labels_model, match_not_null.group(1)))
                else:
                    _raise_bad_labels_filter(labels_filter)

            else:
                _raise_bad_labels_filter(labels_filter)

        except ValueError:
            _raise_bad_labels_filter(labels_filter)

    return query


def _raise_bad_labels_filter(labels_filter_value):
    raise manager_exceptions.BadParametersError(
        'The labels filter `{0}` is not in the right '
        'format. It must be one of: <key>=<value>, '
        '<key>=[<value1>,<value2>,...], <key>!=<value>, '
        '<key>!=[<value1>,<value2>,...], <key> is null, '
        '<key> is not null'.format(labels_filter_value)
    )


def _get_label_value(raw_label_value):
    # This means `]` and `,` are not allowed in the labels
    match_list = re.match(r'^\[([^]]+)\]$', raw_label_value)
    if match_list:
        return match_list.group(1).split(',')

    return raw_label_value


def key_equal_value(labels_model, label_key, label_value):
    """ <key>=<value> """
    return labels_model._deployment_fk.in_(
        db.session.query(labels_model._deployment_fk)
        .filter(labels_model.key == label_key,
                labels_model.value == label_value)
        .subquery())


def key_equal_list_values(labels_model, label_key, label_value):
    """ <key>=[<val1>,<val2>] """
    return labels_model._deployment_fk.in_(
        db.session.query(labels_model._deployment_fk)
        .filter(labels_model.key == label_key,
                labels_model.value.in_(label_value))
        .subquery())


def key_not_equal_value(labels_model, label_key, label_value):
    """ <key>!=<val> """
    return labels_model._deployment_fk.in_(
        db.session.query(labels_model._deployment_fk)
        .filter(labels_model.key == label_key,
                labels_model.value != label_value)
        .subquery())


def key_not_equal_list_values(labels_model, label_key, label_value):
    """ <key>!=[<val1>,<val1>] """
    return labels_model._deployment_fk.in_(
        db.session.query(labels_model._deployment_fk)
        .filter(labels_model.key == label_key,
                ~labels_model.value.in_(label_value))
        .subquery())


def key_not_exist(labels_model, label_key):
    """ <key> is null """
    return ~labels_model._deployment_fk.in_(
        _labels_key_subquery(labels_model, label_key))


def key_exist(labels_model, label_key):
    """ <key> is not null """
    return labels_model._deployment_fk.in_(
        _labels_key_subquery(labels_model, label_key))


def _labels_key_subquery(labels_model, label_key):
    return (db.session.query(labels_model._deployment_fk)
            .filter(labels_model.key == label_key)
            .subquery())

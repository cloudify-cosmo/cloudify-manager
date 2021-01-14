from manager_rest.storage.models_base import db
from manager_rest.constants import EQUAL, NOT_EQUAL, IS_NULL, IS_NOT_NULL


def add_labels_filters_to_query(query, labels_model, labels_filters):
    query = query.join(labels_model)

    for label_key, label_values in labels_filters.get(EQUAL, {}).items():
        query = query.filter(key_equal_value(
            labels_model, label_key, label_values))

    for label_key, label_values in labels_filters.get(NOT_EQUAL, {}).items():
        query = query.filter(key_not_equal_value(
            labels_model, label_key, label_values))

    for label_key in labels_filters.get(IS_NULL, []):
        query = query.filter(key_not_exist(labels_model, label_key))

    for label_key in labels_filters.get(IS_NOT_NULL, []):
        query = query.filter(key_exist(labels_model, label_key))

    return query


def key_equal_value(labels_model, label_key, label_value):
    """ <key>=[<val1>,<val2>] """
    return labels_model._deployment_fk.in_(
        db.session.query(labels_model._deployment_fk)
        .filter(labels_model.key == label_key,
                labels_model.value.in_(label_value))
        .subquery())


def key_not_equal_value(labels_model, label_key, label_value):
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

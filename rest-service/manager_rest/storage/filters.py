from manager_rest.storage.models_base import db
from manager_rest.manager_exceptions import BadFilterRule
from manager_rest.constants import FilterRuleType, LabelsOperator


def add_filter_rules_to_query(query, labels_model, filter_rules):
    query = query.join(labels_model).distinct()
    for filter_rule in filter_rules:
        filter_rule_type = filter_rule['type']
        if filter_rule_type == FilterRuleType.LABEL:
            query = add_labels_filter_to_query(query, labels_model,
                                               filter_rule)
        elif filter_rule_type == FilterRuleType.ATTRIBUTE:
            query = add_attrs_filter_to_query(query, filter_rule)
        else:
            raise BadFilterRule(filter_rule)

    return query


def add_attrs_filter_to_query(query, filter_rule):
    return query


def add_labels_filter_to_query(query, labels_model, filter_rule):
    filter_rule_operator = filter_rule['operator']
    filter_rule_key = filter_rule['key']
    filter_rule_values = filter_rule['values']

    if filter_rule_operator == LabelsOperator.ANY_OF:
        query = query.filter(key_any_of_values(
            labels_model, filter_rule_key, filter_rule_values))

    elif filter_rule_operator == LabelsOperator.NOT_ANY_OF:
        query = query.filter(key_not_any_of_values(
            labels_model, filter_rule_key, filter_rule_values))

    elif filter_rule_operator == LabelsOperator.IS_NULL:
        query = query.filter(key_not_exist(labels_model, filter_rule_key))

    elif filter_rule_operator == LabelsOperator.IS_NOT_NULL:
        query = query.filter(key_exist(labels_model, filter_rule_key))

    else:
        raise BadFilterRule(filter_rule)

    return query


def key_any_of_values(labels_model, label_key, label_values):
    """ <key>=[<val1>,<val2>] """
    return labels_model._labeled_model_fk.in_(
        db.session.query(labels_model._labeled_model_fk)
        .filter(labels_model.key == label_key,
                labels_model.value.in_(label_values))
        .subquery())


def key_not_any_of_values(labels_model, label_key, label_values):
    """ <key>!=[<val1>,<val1>] """
    return labels_model._labeled_model_fk.in_(
        db.session.query(labels_model._labeled_model_fk)
        .filter(labels_model.key == label_key,
                ~labels_model.value.in_(label_values))
        .subquery())


def key_not_exist(labels_model, label_key):
    """ <key> is null """
    return ~labels_model._labeled_model_fk.in_(
        _labels_key_subquery(labels_model, label_key))


def key_exist(labels_model, label_key):
    """ <key> is not null """
    return labels_model._labeled_model_fk.in_(
        _labels_key_subquery(labels_model, label_key))


def _labels_key_subquery(labels_model, label_key):
    return (db.session.query(labels_model._labeled_model_fk)
            .filter(labels_model.key == label_key)
            .subquery())

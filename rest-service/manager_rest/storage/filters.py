from sqlalchemy import and_, or_

from manager_rest.storage.models_base import db
from manager_rest.manager_exceptions import BadFilterRule
from manager_rest.constants import (AttrsOperator,
                                    FilterRuleType,
                                    LabelsOperator)

from .utils import get_column, get_joins


def add_filter_rules_to_query(query, model_class, filter_rules):
    labels_join_added = False
    joined_columns_set = set()
    labels_model = model_class.labels_model
    for filter_rule in filter_rules:
        filter_rule_type = filter_rule['type']
        if filter_rule_type == FilterRuleType.LABEL:
            if not labels_join_added:
                query = query.outerjoin(
                    labels_model,
                    labels_model._labeled_model_fk == model_class._storage_id)\
                    .distinct()
                labels_join_added = True
            query = add_labels_filter_to_query(query,
                                               model_class,
                                               labels_model,
                                               filter_rule)
        elif filter_rule_type == FilterRuleType.ATTRIBUTE:
            query = add_attrs_filter_to_query(query, model_class, filter_rule,
                                              joined_columns_set)
        else:
            raise BadFilterRule(filter_rule)

    return query


def add_attrs_filter_to_query(query, model_class, filter_rule,
                              joined_columns_set):
    filter_rule_operator = filter_rule['operator']
    column_name = filter_rule['key']
    filter_rule_values = filter_rule['values']

    column = get_column(model_class, column_name)
    if column_name not in joined_columns_set:
        joined_columns_set.add(column_name)
        join = get_joins(model_class, [column_name])
        query = query.outerjoin(*join)
    if filter_rule_operator == AttrsOperator.ANY_OF:
        query = query.filter(column.in_(filter_rule_values))

    elif filter_rule_operator == AttrsOperator.NOT_ANY_OF:
        query = query.filter(~column.in_(filter_rule_values))

    elif filter_rule_operator == AttrsOperator.CONTAINS:
        if len(filter_rule_values) == 1:
            query = query.filter(column.contains(filter_rule_values[0]))
        else:
            contain_filter = (column.contains(value) for value in
                              filter_rule_values)
            query = query.filter(or_(*contain_filter))

    elif filter_rule_operator == AttrsOperator.NOT_CONTAINS:
        if len(filter_rule_values) == 1:
            query = query.filter(~column.contains(filter_rule_values[0]))
        else:
            contain_filter = (~column.contains(value) for value in
                              filter_rule_values)
            query = query.filter(and_(*contain_filter))

    elif filter_rule_operator == AttrsOperator.STARTS_WITH:
        if len(filter_rule_values) == 1:
            query = query.filter(column.ilike(f'{filter_rule_values[0]}%'))
        else:
            like_filter = (column.ilike(f'{value}%') for value in
                           filter_rule_values)
            query = query.filter(or_(*like_filter))

    elif filter_rule_operator == AttrsOperator.ENDS_WITH:
        if len(filter_rule_values) == 1:
            query = query.filter(column.ilike(f'%{filter_rule_values[0]}'))
        else:
            like_filter = (column.ilike(f'%{value}') for value in
                           filter_rule_values)
            query = query.filter(or_(*like_filter))

    elif filter_rule_operator == AttrsOperator.IS_NOT_EMPTY:
        try:
            query = query.filter(column.isnot(None))\
                .filter(~column.in_(['', [], '{}']))
        except NotImplementedError:
            # if the column represents a relationship, in_() is not supported:
            # use RelationshipProperty.Comparator.any() instead
            query = query.filter(column.any())

    else:
        raise BadFilterRule(filter_rule)

    return query


def add_labels_filter_to_query(query, model_class, labels_model, filter_rule):
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
        query = query.filter(
            key_not_exist(model_class, labels_model, filter_rule_key))

    elif filter_rule_operator == LabelsOperator.IS_NOT_NULL:
        query = query.filter(key_exist(labels_model, filter_rule_key))

    elif filter_rule_operator == LabelsOperator.IS_NOT:
        query = query.filter(key_not_any_of_values_or_not_exist(
            model_class, labels_model, filter_rule_key, filter_rule_values))

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


def key_not_any_of_values_or_not_exist(model_class, labels_model, label_key,
                                       label_values):
    """
    <key>!=[<val1>,<val1>] or
    the resource doesn't have a label with the key <key> (<key> is null)
    """
    return ~model_class._storage_id.in_(
        db.session.query(labels_model._labeled_model_fk)
        .filter(labels_model.key == label_key,
                labels_model.value.in_(label_values))
        .subquery()
    )


def key_not_exist(model_class, labels_model, label_key):
    """ <key> is null """
    return ~model_class._storage_id.in_(
        _labels_key_subquery(labels_model, label_key))


def key_exist(labels_model, label_key):
    """ <key> is not null """
    return labels_model._labeled_model_fk.in_(
        _labels_key_subquery(labels_model, label_key))


def _labels_key_subquery(labels_model, label_key):
    return (db.session.query(labels_model._labeled_model_fk)
            .filter(labels_model.key == label_key)
            .subquery())

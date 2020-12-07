import re
import ast

from sqlalchemy import and_ as sql_and

from cloudify._compat import text_type

from manager_rest import manager_exceptions
from manager_rest.storage.models_base import db


class LabelsFilters(object):
    def __init__(self, raw_labels_filters_list):
        self.labels_filters_list = self._create_labels_filters_list(
            raw_labels_filters_list)

    def _create_labels_filters_list(self, raw_labels_filters_list):
        labels_filters_list = []
        for labels_filter in raw_labels_filters_list:
            try:
                if '!=' in labels_filter:
                    label_key, label_value = labels_filter.split('!=')
                    if self._is_label_value_list(label_value):
                        labels_filters_list.append(
                            KeyNotEqualListValues(
                                label_key, ast.literal_eval(label_value)
                            ))
                    else:
                        labels_filters_list.append(
                            KeyNotEqualValue(label_key, label_value))

                elif '=' in labels_filter:
                    label_key, label_value = labels_filter.split('=')
                    if self._is_label_value_list(label_value):
                        labels_filters_list.append(
                            KeyEqualListValues(
                                label_key, ast.literal_eval(label_value)
                            ))
                    else:
                        labels_filters_list.append(
                            KeyEqualValue(label_key, label_value))

                elif 'null' in labels_filter:
                    if re.match(r'\S+ is null', labels_filter):
                        labels_filters_list.append(
                            KeyNotExist(labels_filter.split()[0], None))
                    elif re.match(r'\S+ is not null', labels_filter):
                        labels_filters_list.append(
                            KeyExist(labels_filter.split()[0], None))
                    else:
                        self.raise_bad_labels_filter(labels_filter)

            except SyntaxError:
                self.raise_bad_labels_filter(labels_filter)

        return labels_filters_list

    @staticmethod
    def raise_bad_labels_filter_value(labels_filter_value):
        raise manager_exceptions.BadParametersError(
            'The labels filter value `{0}` must be a string or a list '
            'of strings'.format(labels_filter_value)
        )

    @staticmethod
    def raise_bad_labels_filter(labels_filter_value):
        raise manager_exceptions.BadParametersError(
            'The labels filter `{0}` is not in the right '
            'format. It must be one of: <key>=<value>, '
            '<key>=[<value1>, <value2>, ...], <key>!=<value>, '
            '<key>!=[<value1>, <value2>, ...], <key> is null, '
            '<key> is not null'.format(labels_filter_value)
        )

    def _is_label_value_list(self, raw_label_value):
        try:
            label_value = ast.literal_eval(raw_label_value)
            if isinstance(label_value, list):
                return True
            else:
                self.raise_bad_labels_filter_value(raw_label_value)
        except ValueError:
            if isinstance(raw_label_value, text_type):
                return False
            else:
                self.raise_bad_labels_filter_value(raw_label_value)
        except SyntaxError:
            self.raise_bad_labels_filter_value(raw_label_value)

    def add_labels_filters_to_query(self, query, labels_model):
        query = query.join(labels_model)
        for labels_filter in self.labels_filters_list:
            query = query.filter(labels_filter.get_query_filter(labels_model))

        return query


class LabelsFilter(object):
    def __init__(self, label_key, label_value):
        self.label_key = label_key
        self.label_value = label_value

    def get_query_filter(self, labels_model):
        raise NotImplementedError()


class KeyEqualValue(LabelsFilter):
    """ <key>=<value> """
    def __init__(self, label_key, label_value):
        super(KeyEqualValue, self).__init__(label_key, label_value)

    def get_query_filter(self, labels_model):
        return sql_and(labels_model.key == self.label_key,
                       labels_model.value == self.label_value)


class KeyEqualListValues(LabelsFilter):
    """ <key>=[<val1>,<val2>] """
    def __init__(self, label_key, label_value):
        super(KeyEqualListValues, self).__init__(label_key, label_value)

    def get_query_filter(self, labels_model):
        return sql_and(labels_model.key == self.label_key,
                       labels_model.value.in_(self.label_value))


class KeyNotEqualValue(LabelsFilter):
    """ <key>!=<val> """
    def __init__(self, label_key, label_value):
        super(KeyNotEqualValue, self).__init__(label_key, label_value)

    def get_query_filter(self, labels_model):
        return sql_and(labels_model.key == self.label_key,
                       labels_model.value != self.label_value)


class KeyNotEqualListValues(LabelsFilter):
    """ <key>!=[<val1>,<val1>] """
    def __init__(self, label_key, label_value):
        super(KeyNotEqualListValues, self).__init__(label_key, label_value)

    def get_query_filter(self, labels_model):
        return sql_and(labels_model.key == self.label_key,
                       ~labels_model.value.in_(self.label_value))


class KeyNotExist(LabelsFilter):
    """ <key> is null """
    def __init__(self, label_key, label_value):
        super(KeyNotExist, self).__init__(label_key, label_value)

    def get_query_filter(self, labels_model):
        subquery = (db.session.query(labels_model._deployment_fk)
                    .filter(labels_model.key == self.label_key)
                    .subquery())
        return ~labels_model._deployment_fk.in_(subquery)


class KeyExist(LabelsFilter):
    """ <key> is not null """
    def __init__(self, label_key, label_value):
        super(KeyExist, self).__init__(label_key, label_value)

    def get_query_filter(self, labels_model):
        subquery = (db.session.query(labels_model._deployment_fk)
                    .filter(labels_model.key == self.label_key)
                    .subquery())
        return labels_model._deployment_fk.in_(subquery)

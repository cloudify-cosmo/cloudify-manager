import re
import json
from flask import request

from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.utils import get_formatted_timestamp
from manager_rest.rest import rest_decorators, rest_utils
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager, filters

from .deployments import LABEL_LEN


class Filters(SecuredResource):
    @authorize('filters_list')
    @rest_decorators.marshal_with(models.Filter)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.Filter)
    @rest_decorators.all_tenants
    @rest_decorators.search('id')
    def get(self, _include=None, pagination=None, sort=None,
            all_tenants=None, search=None):
        """List filters"""

        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        result = get_storage_manager().list(
            models.Filter,
            include=_include,
            substr_filters=search,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )

        return result


class FiltersId(SecuredResource):
    @authorize('filters_create')
    @rest_decorators.marshal_with(models.Filter)
    def put(self, filter_id):
        """Create a filter

        Currently, this function only supports the creation of a labels filter
        """
        rest_utils.validate_inputs({'filter_id': filter_id})
        request_dict = rest_utils.get_json_and_verify_params(
            {'filter_rules': {'type': list}})
        labels_filters = request_dict['filter_rules']
        parsed_labels_filters = _parse_labels_filters(labels_filters)
        visibility = rest_utils.get_visibility_parameter(
            optional=True, valid_values=VisibilityState.STATES)

        new_filter = models.Filter(
            id=filter_id,
            value=json.dumps({'labels': parsed_labels_filters}),
            created_at=get_formatted_timestamp(),
            visibility=visibility
        )

        return get_storage_manager().put(new_filter)


def _parse_labels_filters(labels_filters_list):
    """Validate and parse a list of labels filters

    :param labels_filters_list: A list of labels filters. Labels filters must
           be one of: <key>=<value>, <key>=[<value1>,<value2>,...],
           <key>!=<value>, <key>!=[<value1>,<value2>,...], <key> is null,
           <key> is not null

    :return The labels filters list with the labels' keys and values in
            lowercase and stripped of whitespaces
    """
    parsed_filter = None
    parsed_labels_filters = []
    for labels_filter in labels_filters_list:
        try:
            if '!=' in labels_filter:
                parsed_filter = _parse_labels_filter(labels_filter, '!=')

            elif '=' in labels_filter:
                parsed_filter = _parse_labels_filter(labels_filter, '=')

            elif 'null' in labels_filter:
                match_null = re.match(r'(\S+) is null', labels_filter)
                match_not_null = re.match(r'(\S+) is not null', labels_filter)
                if match_null:
                    parsed_filter = match_null.group(1).lower() + ' is null'
                elif match_not_null:
                    parsed_filter = (match_not_null.group(1).lower() +
                                     ' is not null')
                else:
                    filters.raise_bad_labels_filter(labels_filter)

            else:
                filters.raise_bad_labels_filter(labels_filter)

        except ValueError:
            filters.raise_bad_labels_filter(labels_filter)

        if parsed_filter:
            parsed_labels_filters.append(parsed_filter)

    return parsed_labels_filters


def _parse_labels_filter(labels_filter, sign):
    """Validate and parse a labels filter

    :param labels_filter: One of <key>=<value>, <key>=[<value1>,<value2>,...],
           <key>!=<value>, <key>!=[<value1>,<value2>,...]
    :param sign: Either '=' or '!='
    :return: The labels_filter, with its key and value(s) in lowercase and
             stripped of whitespaces
    """
    label_key, raw_label_value = labels_filter.split(sign)
    label_value = filters.get_label_value(raw_label_value.strip())
    if isinstance(label_value, list):
        value_msg_prefix = 'One of the filter values'
        label_values_list = label_value
    else:
        value_msg_prefix = None
        label_values_list = [label_value]
    for value in label_values_list:
        try:
            rest_utils.validate_inputs(
                {'filter key': label_key.strip()}, len_input_value=LABEL_LEN)
            rest_utils.validate_inputs(
                {'filter value': value.strip()}, len_input_value=LABEL_LEN,
                err_prefix=value_msg_prefix)
        except manager_exceptions.BadParametersError as e:
            err_msg = 'The filter rule {0} is invalid. '.format(labels_filter)
            raise manager_exceptions.BadParametersError(err_msg + str(e))

    parsed_values_list = [value.strip().lower() for value in label_values_list]
    parsed_value = (('[' + ','.join(parsed_values_list) + ']')
                    if isinstance(label_value, list) else
                    parsed_values_list[0])
    return label_key.strip().lower() + sign + parsed_value

#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from functools import wraps
from collections import OrderedDict

from dateutil.parser import parse as parse_datetime
from flask_restful import marshal
from flask_restful.utils import unpack
from flask import request, current_app
from sqlalchemy.util._collections import _LW as sql_alchemy_collection
from toolz import (
    dicttoolz,
    functoolz,
)
from voluptuous import (
    All,
    Any,
    Coerce,
    ExactSequence,
    Invalid,
    Length,
    Match,
    REMOVE_EXTRA,
    Range,
    Schema,
)

from ..security.authentication import authenticator
from manager_rest import utils, config, manager_exceptions
from manager_rest.rest.rest_utils import verify_and_convert_bool
from manager_rest.storage.models_base import SQLModelBase

from .responses_v2 import ListResponse

INCLUDE = 'Include'
SORT = 'Sort'
FILTER = 'Filter'


def _validate_fields(valid_fields, fields_to_check, action):
    """Assert that `fields_to_check` is a subset of `valid_fields`

    :param valid_fields: A list/dict of valid fields
    :param fields_to_check: A list/dict of fields to check
    :param action: The action being performed (Sort/Include/Filter)
    """
    error_type = {INCLUDE: manager_exceptions.NoSuchIncludeFieldError,
                  SORT: manager_exceptions.BadParametersError,
                  FILTER: manager_exceptions.BadParametersError}
    unknowns = [k for k in fields_to_check if k not in valid_fields]
    if unknowns:
        raise error_type[action](
            '{action} keys \'{key_names}\' do not exist. Allowed '
            'keys are: {fields}'
            .format(
                action=action,
                key_names=unknowns,
                fields=list(valid_fields))
        )


# region V1 decorators

def insecure_rest_method(func):
    """block an insecure REST method if manager disabled insecure endpoints
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if config.instance.insecure_endpoints_disabled:
            raise manager_exceptions.MethodNotAllowedError()
        return func(*args, **kwargs)
    return wrapper


def exceptions_handled(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            try:
                return func(*args, **kwargs)
            except Invalid as e:
                # Re-raise voluptuous validation errors
                # to handle them properly in the outer try/excep block
                raise manager_exceptions.BadParametersError(e.error_message)
        except manager_exceptions.ManagerException as e:
            utils.abort_error(e, current_app.logger)
    return wrapper


class marshal_with(object):
    def __init__(self, response_class):
        """
        :param response_class: response class to marshal result with.
         class must have a "resource_fields" class variable
        """
        if hasattr(response_class, 'response_fields'):
            self._fields = response_class.response_fields
        elif hasattr(response_class, 'resource_fields'):
            self._fields = response_class.resource_fields
        else:
            raise RuntimeError(
                'Response class {0} does not contain a "resource_fields" '
                'class variable'.format(type(response_class)))

        self.response_class = response_class

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if hasattr(request, '__skip_marshalling'):
                return f(*args, **kwargs)

            fields_to_include = self._get_fields_to_include()
            if self._is_include_parameter_in_request():
                # only pushing "_include" into kwargs when the request
                # contained this parameter, to keep things cleaner (identical
                # behavior for passing "_include" which contains all fields)
                kwargs['_include'] = fields_to_include.keys()

            response = f(*args, **kwargs)

            if isinstance(response, ListResponse):
                wrapped_items = self.wrap_with_response_object(response.items)
                response.items = marshal(wrapped_items, fields_to_include)
                return marshal(response, ListResponse.resource_fields)
            # SQLAlchemy returns a class that subtypes tuple, but acts
            # differently (it's taken care of in `wrap_with_response_object`)
            if isinstance(response, tuple) and \
                    not isinstance(response, sql_alchemy_collection):
                data, code, headers = unpack(response)
                data = self.wrap_with_response_object(data)
                return marshal(data, fields_to_include), code, headers
            else:
                response = self.wrap_with_response_object(response)
                return marshal(response, fields_to_include)

        return wrapper

    def wrap_with_response_object(self, data):
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            return map(self.wrap_with_response_object, data)
        elif isinstance(data, SQLModelBase):
            return data.to_response(get_data=self._get_data())
        # Support for partial results from SQLAlchemy (i.e. only
        # certain columns, and not the whole model class)
        elif isinstance(data, sql_alchemy_collection):
            return data._asdict()
        raise RuntimeError('Unexpected response data (type {0}) {1}'.format(
            type(data), data))

    @staticmethod
    def _is_include_parameter_in_request():
        return '_include' in request.args and request.args['_include']

    @staticmethod
    def _get_data():
        get_data = request.args.get('_get_data', False)
        return verify_and_convert_bool('get_data', get_data)

    def _get_fields_to_include(self):
        skipped_fields = self._get_skipped_fields()
        model_fields = {k: v for k, v in self._fields.iteritems()
                        if k not in skipped_fields}

        if self._is_include_parameter_in_request():
            include = set(request.args['_include'].split(','))
            _validate_fields(model_fields, include, INCLUDE)
            include_fields = {k: v for k, v in model_fields.iteritems()
                              if k in include}
            return include_fields
        return model_fields

    @staticmethod
    def _get_api_version():
        url = request.base_url
        if 'api' not in url:
            return None
        version = url.split('/api/')[1]
        return version.split('/')[0]

    def _get_skipped_fields(self):
        api_version = self._get_api_version()
        if hasattr(self.response_class, 'skipped_fields'):
            return self.response_class.skipped_fields.get(api_version, [])
        return []

# endregion


# region V2 decorators

def projection(func):
    """Decorator for enabling projection
    """
    @wraps(func)
    def create_projection_params(*args, **kw):
        projection_params = None
        if '_include' in request.args:
            projection_params = request.args["_include"].split(',')
        return func(_include=projection_params, *args, **kw)
    return create_projection_params


def rangeable(func):
    """Decorator for enabling filtering by a range of values.

    Range filtering is expected to be passed in the `_range` header as a list
    of triplets with the following values separated by commmas:
        - Field: The name of the field to filter by
        - From: The minimum value to include in the results
        - To: The maxium value to include in the results

    The range filters are mapped to a dictionary where the keys are the names
    of the fields to filter and the values are dictionaries that have
    `from`/`to` as fields with their values.

    :param func:
        The function to be wrapped. It is assumed that the function will be
        implementing an endpoint.
    :type func: callable
    :returns:
        Decorated function in which the `range_filters` parameter is injected
        with the values from the `_range` headers mapped to a dictionary as
        explained above.
    :rtype: callable

    """
    def valid_datetime(datetime):
        """Make sure that datetime is parseable.

        :param datetime: Datetime value to parse
        :type datetime: str
        :return: The datetime value after parsing
        :rtype: :class:`datetime.datetime`

        """
        try:
            parsed_datetime = parse_datetime(datetime)
        except Exception:
            raise Invalid('Datetime parsing error')

        return parsed_datetime

    def from_or_to_present(range_param):
        """Make sure that at least one of from or to are present.

        :param range_param: Range parameter splitted at the commas
        :type range_param: tuple(str, str, str)
        :return: The same value that was passed
        :rtype: tuple(str, str, str)

        """
        field, from_, to = range_param
        if not (from_ or to):
            raise Invalid('At least one of from/to must be passed')
        return range_param

    schema = Schema(
        All(
            ExactSequence([
                basestring,
                Any(valid_datetime, ''),
                Any(valid_datetime, ''),
            ]),
            Length(min=3, max=3),
            from_or_to_present,
            msg=(
                'Range parameter should be formatted as follows: '
                '<field:str>,[<from:datetime>],[<to:datetime>]\n'
                'Where from/to are optional, '
                'but at least one of them must be passed'
            )
        )
    )

    @wraps(func)
    def create_range_params(*args, **kw):
        range_args = request.args.getlist('_range')
        range_params = [
            schema(range_arg.split(','))
            for range_arg in range_args
        ]
        range_filters = {
            range_param[0]: dicttoolz.valfilter(
                functoolz.identity,
                {
                    'from': range_param[1],
                    'to': range_param[2],
                })
            for range_param in range_params
        }
        return func(range_filters=range_filters, *args, **kw)
    return create_range_params


def sortable(response_class=None):
    """Decorator for enabling sort.

    This decorator looks into the request for one or more `_sort` parameters
    and maps them into a dictionary in which keys are column names and the
    values are the ordering (either `asc` for ascending or `desc` descending).
    The parameter values are expected to be strings with the column name
    prefixed with either `+` or `-` to set the ordering (being `+` the default
    in absence of any prefix).

    Once the request parameters have been transformed into the dictionary
    object it's passed as the `sort` parameter to the decorated function.

    A `voluptuous.error.Invalid` exception will be raised if any of the request
    parameters has an invalid value.
    """
    fields = response_class.resource_fields if response_class else {}

    schema = Schema(
        [
            Match(
                # `@` allowed for compatibility with elasticsearch fields
                r'[+-]?[\w@]+',
                msg=(
                    '`_sort` parameter should be a column name '
                    'optionally prefixed with +/-'
                ),
            ),
        ],
        extra=REMOVE_EXTRA,
    )

    def sortable_dec(func):
        @wraps(func)
        def create_sort_params(*args, **kw):
            """Validate sort parameters and pass them to the wrapped function.
            """
            # maintain order of sort fields
            sort_params = OrderedDict([
                (
                    param.lstrip('+-'),
                    'desc' if param[0] == '-' else 'asc',
                )
                for param in schema(request.args.getlist('_sort'))
            ])
            if fields:
                _validate_fields(fields, sort_params, SORT)
            return func(sort=sort_params, *args, **kw)
        return create_sort_params
    return sortable_dec


def all_tenants(func):
    """
    Decorator for enabling sort
    """
    @wraps(func)
    def is_all_tenants(*args, **kw):
        all_tenants_flag = verify_and_convert_bool(
            'all_tenants', request.args.get('_all_tenants', False))
        return func(all_tenants=all_tenants_flag, *args, **kw)
    return is_all_tenants


def marshal_events(func):
    """
    Decorator for marshalling raw event responses
    """
    @wraps(func)
    def marshal_response(*args, **kwargs):
        return marshal(func(*args, **kwargs), ListResponse.resource_fields)
    return marshal_response


def paginate(func):
    """Decorator for adding pagination.

    This decorator looks into the request for the `_size` and `_offset`
    parameters and passes them as the `paginate` parameter to the decorated
    function.

    The `paginate` parameter is a dictionary whose keys are `size` and `offset`
    (note that the leading underscore is dropped) if a values was passed in a
    request header. Otherwise, the dictionary will be empty.

    A `voluptuous.error.Invalid` exception will be raised if any of the request
    parameters has an invalid value.

    :param func: Function to be decorated
    :type func: callable

    """
    schema = Schema(
        {
            '_size': All(
                Coerce(int),
                Range(min=0),
                msg='`_size` is expected to be a positive integer',
            ),
            '_offset': All(
                Coerce(int),
                Range(min=0),
                msg='`_offset` is expected to be a positive integer',
            ),
        },
        extra=REMOVE_EXTRA,
    )

    @wraps(func)
    def verify_and_create_pagination_params(*args, **kw):
        """Validate pagination parameters and pass them to wrapped function."""
        pagination_params = dicttoolz.keymap(
            # Drop leading underscore from keys
            lambda key: key.lstrip('_'),
            schema(request.args),
        )
        result = func(pagination=pagination_params, *args, **kw)
        return ListResponse(items=result.items, metadata=result.metadata)

    return verify_and_create_pagination_params


def create_filters(response_class=None):
    """
    Decorator for extracting filter parameters from the request arguments and
    optionally verifying their validity according to the provided fields.
    :param response_class: The response class to be marshalled with
    :return: a Decorator for creating and validating the accepted fields.
    """
    fields = response_class.resource_fields if response_class else {}

    def create_filters_dec(f):
        @wraps(f)
        def some_func(*args, **kw):
            request_args = request.args.to_dict(flat=False)
            # NOTE: all filters are created as lists
            filters = {k: v for k, v in
                       request_args.iteritems() if not k.startswith('_')}
            if fields:
                _validate_fields(fields, filters.iterkeys(), FILTER)
            return f(filters=filters, *args, **kw)
        return some_func
    return create_filters_dec

# endregion


# region V3 decorators

def evaluate_functions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        val = request.args.get('_evaluate_functions', False)
        val = verify_and_convert_bool('_evaluate_functions', val)
        kwargs['evaluate_functions'] = val
        return func(*args, **kwargs)
    return wrapper


def no_ldap(action):
    def no_ldap_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if authenticator.ldap:
                raise manager_exceptions.IllegalActionError(
                    'Action `{0}` is not available in ldap mode'.format(action)
                )
            return func(*args, **kwargs)
        return wrapper
    return no_ldap_dec

# endregion

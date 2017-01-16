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

from flask_restful import marshal
from flask_restful.utils import unpack
from flask import request, current_app
from sqlalchemy.util._collections import _LW as sql_alchemy_collection
from toolz import dicttoolz
from voluptuous import (
    All,
    Coerce,
    Invalid,
    Match,
    REMOVE_EXTRA,
    Range,
    Schema,
)

from manager_rest import utils, config, manager_exceptions
from manager_rest.storage.models_base import SQLModelBase

from .responses_v2 import ListResponse
from .rest_utils import skip_nested_marshalling


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
    def __init__(self, response_class, include_fields=None, skip_fields=None):
        """
        :param response_class: response class to marshal result with.
         class must have a "resource_fields" class variable
        """
        if response_class and not hasattr(response_class, 'resource_fields'):
            raise RuntimeError(
                'Response class {0} does not contain a "resource_fields" '
                'class variable'.format(type(response_class)))

        if include_fields and skip_fields:
            raise RuntimeError('Both `include_fields` and `skip_fields` '
                               'passed to class {0}'.format(response_class))

        self.response_class = response_class

        if include_fields:
            fields = response_class.get_fields(include_fields)
        else:
            fields = response_class.resource_fields

        if skip_fields:
            fields = {k: v for k, v in fields.items() if k not in skip_fields}

        self.fields = fields

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if hasattr(request, '__skip_marshalling'):
                return f(*args, **kwargs)

            fields_to_include = self._get_fields_to_include(
                self.response_class,
                self.fields
            )
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
            return data.to_response()
        # Support for partial results from SQLAlchemy (i.e. only
        # certain columns, and not the whole model class)
        elif isinstance(data, sql_alchemy_collection):
            return data._asdict()
        raise RuntimeError('Unexpected response data (type {0}) {1}'.format(
            type(data), data))

    @staticmethod
    def _is_include_parameter_in_request():
        return '_include' in request.args and request.args['_include']

    def _get_fields_to_include(self, response_class, model_fields):
        skipped_fields = self._get_skipped_fields(response_class)
        model_fields = {k: v for k, v in model_fields.iteritems()
                        if k not in skipped_fields}

        if self._is_include_parameter_in_request():
            include = set(request.args['_include'].split(','))
            include_fields = {}
            illegal_fields = None
            for field in include:
                if field not in model_fields:
                    if not illegal_fields:
                        illegal_fields = []
                    illegal_fields.append(field)
                    continue
                include_fields[field] = model_fields[field]
            if illegal_fields:
                raise manager_exceptions.NoSuchIncludeFieldError(
                    'Illegal include fields: [{}] - available fields: '
                    '[{}]'.format(', '.join(illegal_fields),
                                  ', '.join(model_fields.keys())))
            return include_fields
        return model_fields

    @staticmethod
    def _get_api_version():
        url = request.base_url
        if 'api' not in url:
            return None
        version = url.split('/api/')[1]
        return version.split('/')[0]

    def _get_skipped_fields(self, response_class):
        api_version = self._get_api_version()
        if hasattr(response_class, 'skipped_fields'):
            return response_class.skipped_fields.get(api_version, [])
        return []

# endregion


# region V2 decorators

def projection(func):
    """Decorator for enabling projection
    """
    def create_projection_params(*args, **kw):
        projection_params = None
        if '_include' in request.args:
            projection_params = request.args["_include"].split(',')
        return func(_include=projection_params, *args, **kw)
    return create_projection_params


def rangeable(func):
    """
    Decorator for enabling range
    """
    def create_range_params(*args, **kw):
        range_args = request.args.getlist("_range")
        range_params = {}
        for range_arg in range_args:
            try:
                range_key, range_from, range_to = \
                    range_arg.split(',')
            except ValueError:
                raise ValueError('Range parameter requires 3 values')
            range_param = {}
            if range_from:
                range_param['from'] = range_from
            if range_to:
                range_param['to'] = range_to
            if range_param:
                range_params[range_key] = range_param

        return func(range_filters=range_params, *args, **kw)
    return create_range_params


def sortable(func):
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

    @wraps(func)
    def create_sort_params(*args, **kw):
        """Validate sort parameters and pass them to the wrapped function."""
        # maintain order of sort fields
        sort_params = OrderedDict([
            (
                param.lstrip('+-'),
                'desc' if param[0] == '-' else 'asc',
            )
            for param in schema(request.args.getlist('_sort'))
        ])
        return func(sort=sort_params, *args, **kw)
    return create_sort_params


def all_tenants(func):
    """
    Decorator for enabling sort
    """
    def is_all_tenants(*args, **kw):
        all_tenants_flag = bool(request.args.get("_all_tenants"))
        return func(all_tenants=all_tenants_flag, *args, **kw)
    return is_all_tenants


def marshal_events(func):
    """
    Decorator for marshalling raw event responses
    """
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


def create_filters(fields=None):
    """
    Decorator for extracting filter parameters from the request arguments and
    optionally verifying their validity according to the provided fields.
    :param fields: a set of valid filter fields.
    :return: a Decorator for creating and validating the accepted fields.
    """
    def create_filters_dec(f):
        def some_func(*args, **kw):
            request_args = request.args.to_dict(flat=False)
            # NOTE: all filters are created as lists
            filters = {k: v for k, v in
                       request_args.iteritems() if not k.startswith('_')}
            if fields:
                unknowns = [k for k in filters.iterkeys() if k not in fields]
                if unknowns:
                    raise manager_exceptions.BadParametersError(
                        'Filter keys \'{key_names}\' do not exist. Allowed '
                        'filters are: {fields}'
                        .format(key_names=unknowns, fields=list(fields)))
            return f(filters=filters, *args, **kw)
        return some_func
    return create_filters_dec

# endregion

# region V2.1 decorators


def override_marshal_with(f, model):
    @exceptions_handled
    @marshal_with(model)
    def wrapper(*args, **kwargs):
        with skip_nested_marshalling():
            return f(*args, **kwargs)
    return wrapper

# endregion

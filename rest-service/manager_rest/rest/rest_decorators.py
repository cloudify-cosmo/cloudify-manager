import pytz

from functools import wraps
from collections import OrderedDict
from typing import Dict

from dateutil.parser import parse as parse_datetime
from flask_restful import fields, marshal
from flask_restful.utils import unpack
from flask import request, current_app
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
from cloudify.models_states import ExecutionState
from manager_rest import config, manager_exceptions
from manager_rest.utils import current_tenant
from manager_rest.security.authorization import is_user_action_allowed
from manager_rest.storage.models_base import SQLModelBase, db
from manager_rest.storage.management_models import User
from manager_rest.execution_token import current_execution
from manager_rest.rest.rest_utils import (
    normalize_value,
    verify_and_convert_bool,
    request_use_all_tenants,
    is_system_in_snapshot_restore_process,
    is_deployment_update
)

from .responses_v2 import ListResponse

INCLUDE = 'Include'
SORT = 'Sort'
FILTER = 'Filter'

SPECIAL_CHARS = ['\\', '_', '%']


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


class marshal_with(object):
    def __init__(self, response_class, force_get_data=False):
        """
        :param response_class: response class to marshal result with.
         class must have a "resource_fields" class variable
        """
        try:
            self._fields = response_class.response_fields
        except AttributeError:
            self._fields = response_class.resource_fields

        self.response_class = response_class
        self.force_get_data = force_get_data

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
                kwargs['_include'] = list(fields_to_include.keys())

            response = f(*args, **kwargs)

            def wrap_list_items(response):
                wrapped_items = self.wrap_with_response_object(
                    response.items, fields_to_include)
                if self._include_hash():
                    fields_to_include['password_hash'] = fields.String
                response.items = marshal(wrapped_items, fields_to_include)
                return response

            if isinstance(response, ListResponse):
                return marshal(wrap_list_items(response),
                               ListResponse.resource_fields)
            if isinstance(response, tuple):
                data, code, headers = unpack(response)
                if isinstance(data, ListResponse):
                    data = wrap_list_items(data)
                    return (marshal(data, ListResponse.resource_fields),
                            code,
                            headers)
                else:
                    data = self.wrap_with_response_object(
                        data, fields_to_include)
                    return marshal(data, fields_to_include), code, headers
            else:
                response = self.wrap_with_response_object(
                    response, fields_to_include)
                return marshal(response, fields_to_include)

        return wrapper

    def wrap_with_response_object(self, data, fields_to_include):
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            return [
                self.wrap_with_response_object(item, fields_to_include)
                for item in data
            ]
        elif isinstance(data, SQLModelBase):
            kwargs = {
                'get_data': self._get_data() or self.force_get_data,
                'include': fields_to_include,
            }
            if isinstance(data, User):
                kwargs['include_hash'] = self._include_hash()
            return data.to_response(**kwargs)
        raise RuntimeError('Unexpected response data (type {0}) {1}'.format(
            type(data), data))

    @staticmethod
    def _is_include_parameter_in_request():
        return '_include' in request.args and request.args['_include']

    @staticmethod
    def _get_data():
        get_data = request.args.get('_get_data', False)
        return verify_and_convert_bool('get_data', get_data)

    @staticmethod
    def _include_hash():
        include_hash = request.args.get('_include_hash', False)
        if include_hash and is_user_action_allowed(
                'get_password_hash', None, True):
            return verify_and_convert_bool('include_hash', include_hash)
        return False

    def _get_fields_to_include(self):
        skipped_fields = self._get_skipped_fields()
        model_fields = {k: v for k, v in self._fields.items()
                        if k not in skipped_fields}

        if self._is_include_parameter_in_request():
            include = set(request.args['_include'].split(','))
            _validate_fields(model_fields, include, INCLUDE)
            include_fields = {k: v for k, v in model_fields.items()
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
    of triplets with the following values separated by commas:
        - Field: The name of the field to filter by
        - From: The minimum value to include in the results
        - To: The maximum value to include in the results

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

        # Make sure timestamp is in UTC, but doesn't have any timezone info.
        # Passing timezone aware timestamp to PosgreSQL through SQLAlchemy
        # doesn't seem to work well in manual tests
        if parsed_datetime.tzinfo:
            parsed_datetime = (
                parsed_datetime.astimezone(pytz.timezone('UTC'))
                .replace(tzinfo=None)
            )

        return parsed_datetime

    def from_or_to_present(range_param):
        """Make sure that at least one of from or to are present.

        :param range_param: Range parameter split at the commas
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
                str,
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
        range_filters: Dict[str, Dict[str, str]] = {}
        for key, range_from, range_to in range_params:
            range_filters[key] = {}
            if range_from:
                range_filters[key]['from'] = range_from
            if range_to:
                range_filters[key]['to'] = range_to
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
    Decorator for including all tenants associated with the user
    """
    @wraps(func)
    def is_all_tenants(*args, **kw):
        return func(all_tenants=request_use_all_tenants(), *args, **kw)
    return is_all_tenants


def _get_search_pattern(parameter):
    pattern = request.args.get(parameter)
    if pattern:
        pattern = normalize_value(pattern)
        for char in SPECIAL_CHARS:
            pattern = pattern.replace(char, '\\{0}'.format(char))
    return pattern


def search(attribute):
    """
    Decorator for enabling searching of a resource id by substring
    """
    def search_dec(func):
        @wraps(func)
        def wrapper(*args, **kw):
            pattern = _get_search_pattern('_search')
            search_dict = {attribute: pattern} if pattern else None
            return func(search=search_dict, *args, **kw)
        return wrapper
    return search_dec


def search_multiple_parameters(parameters_dict):
    """
    Decorator for enabling searching of a resource using multiple columns
    :param parameters_dict: A dictionary containing the search parameters as
        keys, and the required attributes as values
    """
    def search_dec(func):
        @wraps(func)
        def wrapper(*args, **kw):
            search_dict: Dict[str, str] = {}
            for param, attribute in parameters_dict.items():
                pattern = _get_search_pattern(param)
                if pattern:
                    search_dict[attribute] = pattern
            return func(search=search_dict or None, *args, **kw)
        return wrapper
    return search_dec


def marshal_list_response(func):
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
        pagination_params = {k.lstrip('_'): v
                             for k, v in schema(request.args).items()}
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
                       request_args.items() if not k.startswith('_')}
            if fields:
                _validate_fields(fields, filters.keys(), FILTER)
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


def no_external_authenticator(action):
    def no_external_authenticator_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if (
                current_app.external_auth
                and current_app.external_auth.configured()
            ):
                raise manager_exceptions.IllegalActionError(
                    'Action `{0}` is not available when '
                    'using external authentication'.format(action)
                )
            return func(*args, **kwargs)
        return wrapper
    return no_external_authenticator_dec

# endregion

# region V3_1 decorators


def prevent_running_in_snapshot_restore(endpoint_func):
    @wraps(endpoint_func)
    def wrapper(*args, **kwargs):
        if is_system_in_snapshot_restore_process():
            raise manager_exceptions.SystemInSnapshotRestoreError()
        return endpoint_func(*args, **kwargs)

    return wrapper


def filter_id(func):
    @wraps(func)
    def get_filter_id(*args, **kw):
        return func(filter_id=request.args.get('_filter_id', None),
                    *args, **kw)
    return get_filter_id

# endregion


def not_while_cancelling(f):
    """This endpoint cannot be called from an execution in a cancelling state

    It's forbidden to call this using an execution token, from an execution
    that is CANCELLING, FORCE_CANCELLING, or KILL_CANCELLING.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_execution and current_execution.status in {
            ExecutionState.CANCELLING,
            ExecutionState.FORCE_CANCELLING,
            ExecutionState.KILL_CANCELLING
        }:
            raise manager_exceptions.ForbiddenWhileCancelling()
        return f(*args, **kwargs)
    return wrapper


def detach_globals(f):
    """Detach current_execution and current_tenant from the db session.

    This means the current_execution and current_tenant objects can be
    used in multiple transactions, and they won't be automatically reloaded
    from the db - saving a query, but not loading additional relationships.

    Use this when access to current_* is limited to direct attributes
    (not relationships) and the request must avoid additional queries
    for performance reasons.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_execution:
            db.session.expunge(current_execution)
        if current_tenant:
            db.session.expunge(current_tenant)
        return f(*args, **kwargs)
    return wrapper


def only_deployment_update(f):
    """Only allow running this request from a deployment-update workflow.

    This prevents the user from updating things in an ad-hoc manner, only
    reserving some update endpoints for the deployment-update workflows.
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_deployment_update():
            raise manager_exceptions.OnlyDeploymentUpdate()
        return f(*args, **kwargs)
    return wrapper

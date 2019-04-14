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

import pytz
import copy
import urllib
import subprocess
import dateutil.parser
from datetime import datetime
from string import ascii_letters
from contextlib import contextmanager

from flask import request, make_response, current_app
from flask_restful.reqparse import Argument, RequestParser

from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions, config
from manager_rest.constants import REST_SERVICE_NAME


states_except_private = copy.deepcopy(VisibilityState.STATES)
states_except_private.remove('private')
VISIBILITY_EXCEPT_PRIVATE = states_except_private


@contextmanager
def skip_nested_marshalling():
    request.__skip_marshalling = True
    yield
    delattr(request, '__skip_marshalling')


def get_json_and_verify_params(params=None):
    params = params or []
    if request.content_type != 'application/json':
        raise manager_exceptions.UnsupportedContentTypeError(
            'Content type must be application/json')

    request_dict = request.json
    is_params_dict = isinstance(params, dict)

    def is_optional(param_name):
        return is_params_dict and params[param_name].get('optional', False)

    def check_type(param_name):
        return is_params_dict and params[param_name].get('type', None)

    for param in params:
        if param not in request_dict:
            if is_optional(param):
                continue
            raise manager_exceptions.BadParametersError(
                'Missing {0} in json request body'.format(param))

        param_type = check_type(param)
        if param_type and not isinstance(request_dict[param], param_type):
            raise manager_exceptions.BadParametersError(
                '{0} parameter is expected to be of type {1} but is of type '
                '{2}'.format(param,
                             param_type.__name__,
                             type(request_dict[param]).__name__))
    return request_dict


def get_args_and_verify_arguments(arguments):
    request_parser = RequestParser()
    for argument in arguments:
        argument.location = 'args'
        request_parser.args.append(argument)
    return request_parser.parse_args()


def verify_and_convert_bool(attribute_name, str_bool):
    if isinstance(str_bool, bool):
        return str_bool
    if isinstance(str_bool, basestring):
        if str_bool.lower() == 'true':
            return True
        if str_bool.lower() == 'false':
            return False
    raise manager_exceptions.BadParametersError(
        '{0} must be <true/false>, got {1}'.format(attribute_name, str_bool))


def convert_to_int(value):
    try:
        return int(value)
    except Exception:
        raise manager_exceptions.BadParametersError(
            'invalid parameter, should be int, got: {0}'.format(value))


def make_streaming_response(res_id, res_path, content_length, archive_type):
    response = make_response()
    response.headers['Content-Description'] = 'File Transfer'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Type'] = 'application/octet-stream'
    response.headers['Content-Disposition'] = \
        'attachment; filename={0}.{1}'.format(res_id, archive_type)
    response.headers['Content-Length'] = content_length
    response.headers['X-Accel-Redirect'] = res_path
    response.headers['X-Accel-Buffering'] = 'yes'
    return response


def set_restart_task(delay=1):
    current_app.logger.info('Restarting the rest service')
    cmd = 'sleep {0}; sudo systemctl restart {1}' \
        .format(delay, REST_SERVICE_NAME)

    subprocess.Popen(cmd, shell=True)


def validate_inputs(input_dict):
    for input_name, input_value in input_dict.iteritems():
        prefix = 'The `{0}` argument'.format(input_name)

        if not input_value:
            raise manager_exceptions.BadParametersError(
                '{0} is empty'.format(prefix)
            )

        if len(input_value) > 256:
            raise manager_exceptions.BadParametersError(
                '{0} is too long. Maximum allowed length is 256 '
                'characters'.format(prefix)
            )

        # urllib.quote changes all chars except alphanumeric chars and _-.
        quoted_value = urllib.quote(input_value, safe='')
        if quoted_value != input_value:
            raise manager_exceptions.BadParametersError(
                '{0} contains illegal characters. Only letters, digits and the'
                ' characters "-", "." and "_" are allowed'.format(prefix)
            )

        if input_value[0] not in ascii_letters:
            raise manager_exceptions.BadParametersError(
                '{0} must begin with a letter'.format(prefix)
            )


def validate_and_decode_password(password):
    if not password:
        raise manager_exceptions.BadParametersError('The password is empty')

    if len(password) > 256:
        raise manager_exceptions.BadParametersError(
            'The password is too long. Maximum allowed length is 256 '
            'characters'
        )

    if len(password) < 5:
        raise manager_exceptions.BadParametersError(
            'The password is too short. Minimum allowed length is 5 '
            'characters'
        )

    return password


def verify_role(role_name, is_system_role=False):
    """Make sure that role name is present in the system.

    :param role_name: Role name to validate against database content.
    :param is_system_role: True if system_role, False if tenant_role
    :raises: BadParametersError when role is not found in the system or is
    not from the right type

    """
    expected_role_type = 'system_role' if is_system_role else 'tenant_role'

    # Get role by name
    role = next(
        (
            r
            for r in config.instance.authorization_roles
            if r['name'] == role_name
        ),
        None
    )

    # Role not found
    if role is None:
        valid_roles = [
            r['name']
            for r in config.instance.authorization_roles
            if r['type'] in (expected_role_type, 'any')
        ]
        raise manager_exceptions.BadParametersError(
            'Invalid role: `{0}`. Valid {1} roles are: {2}'
            .format(role_name, expected_role_type, valid_roles)
        )

    # Role type doesn't match
    if role['type'] not in (expected_role_type, 'any'):
        raise manager_exceptions.BadParametersError(
            'Role `{0}` is a {1} and cannot be assigned as a {2}'
            .format(role_name, role['type'], expected_role_type)
        )


def request_use_all_tenants():
    return verify_and_convert_bool('all_tenants',
                                   request.args.get('_all_tenants', False))


def get_visibility_parameter(optional=False,
                             is_argument=False,
                             valid_values=VISIBILITY_EXCEPT_PRIVATE):
    if is_argument:
        args = get_args_and_verify_arguments(
            [Argument('visibility', default=None)]
        )
        visibility = args.visibility
    else:
        request_dict = get_json_and_verify_params({
            'visibility': {'optional': optional, 'type': unicode}
        })
        visibility = request_dict.get('visibility', None)

    if visibility is not None and visibility not in valid_values:
        raise manager_exceptions.BadParametersError(
            "Invalid visibility: `{0}`. Valid visibility's values are: {1}"
            .format(visibility, valid_values)
        )
    return visibility


def parse_datetime(datetime_str):
    """
    :param datetime_str: A string representing date and time with timezone
                         information.
    :return: A datetime object, converted to UTC, with no timezone info.
    """
    # Parse the string to datetime object
    date_with_offset = dateutil.parser.parse(datetime_str)
    # Convert the date to UTC
    try:
        utc_date = date_with_offset.astimezone(pytz.utc)
    except ValueError:
        raise manager_exceptions.BadParametersError(
            'Date `{0}` missing timezone information, please provide'
            ' valid date. \nExpected format: YYYYMMDDHHMM+HHMM or'
            ' YYYYMMDDHHMM-HHMM i.e: 201801012230-0500'
            ' (Jan-01-18 10:30pm EST)'.format(datetime_str))
    # Date is in UTC, tzinfo is not necessary
    utc_date = utc_date.replace(tzinfo=None)
    now = datetime.utcnow()
    if utc_date <= now:
        raise manager_exceptions.BadParametersError(
            'Date `{0}` has already passed, please provide'
            ' valid date. \nExpected format: YYYYMMDDHHMM+HHMM or'
            ' YYYYMMDDHHMM-HHMM i.e: 201801012230-0500'
            ' (Jan-01-18 10:30pm EST)'.format(datetime_str))

    return utc_date

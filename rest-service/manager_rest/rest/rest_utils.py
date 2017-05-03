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
import urllib
import subprocess
from flask import current_app
from string import ascii_letters

from flask import request, make_response
from flask_restful.reqparse import RequestParser

from contextlib import contextmanager

from manager_rest import manager_exceptions
from manager_rest.constants import REST_SERVICE_NAME


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
    if str_bool.lower() == 'true':
        return True
    if str_bool.lower() == 'false':
        return False
    raise manager_exceptions.BadParametersError(
        '{0} must be <true/false>, got {1}'.format(attribute_name, str_bool))


def convert_to_int(value):
    try:
        return int(value)
    except:
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

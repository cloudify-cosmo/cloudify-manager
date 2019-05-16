# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import functools

from cloudify import ctx
from cloudify.utils import exception_to_error_cause
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.exceptions import NonRecoverableError, OperationRetry


def generate_traceback_exception():
    _, exc_value, exc_traceback = sys.exc_info()
    response = exception_to_error_cause(exc_value, exc_traceback)
    return response


def proxy_operation(operation):
    def decorator(task, **kwargs):
        def wrapper(**kwargs):
            try:
                kwargs['operation'] = operation
                return task(**kwargs)
            except OperationRetry:
                response = generate_traceback_exception()

                ctx.logger.error(
                    'Error traceback {0} with message {1}'.format(
                        response['traceback'], response['message']))

                raise OperationRetry(
                    'Error: {0} while trying to run proxy task {1}'
                    ''.format(response['message'], operation))

            except Exception:
                response = generate_traceback_exception()

                ctx.logger.error(
                    'Error traceback {0} with message {1}'.format(
                        response['traceback'], response['message']))

                raise NonRecoverableError(
                    'Error: {0} while trying to run proxy task {1}'
                    ''.format(response['message'], operation))

        return wrapper
    return decorator


def handle_client_exception(error_msg):
    def exception_decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except CloudifyClientError as ex:
                raise NonRecoverableError(
                    '{0}, due to {1}.'.format(error_msg, str(ex)))
        return wrapper
    return exception_decorator


@handle_client_exception('Deployment search failed')
def get_deployment_by_id(client, deployment_id):
    """
    Searching for deployment_id in all deployments in order to differentiate
    not finding the deployment then other kinds of errors, like server
    failure.
    """
    deployments = client.deployments.list(_include=['id'], id=deployment_id)
    return deployments[0] if deployments else None

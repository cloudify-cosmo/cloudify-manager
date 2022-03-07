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

from cloudify import manager, ctx
from cloudify.utils import exception_to_error_cause
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import ForbiddenWhileCancelling
from cloudify.exceptions import NonRecoverableError, OperationRetry
from cloudify.deployment_dependencies import (dependency_creator_generator,
                                              create_deployment_dependency)


def generate_traceback_exception():
    _, exc_value, exc_traceback = sys.exc_info()
    response = exception_to_error_cause(exc_value, exc_traceback)
    return response


def errors_nonrecoverable(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ForbiddenWhileCancelling:
            raise OperationRetry()
        except Exception as ex:
            response = generate_traceback_exception()

            ctx.logger.error(
                'Error traceback %s with message %s',
                response['traceback'], response['message'])

            raise NonRecoverableError(f'Error in {f.__name__}: {ex}')
    return wrapper


def get_deployment_by_id(client, deployment_id):
    """
    Searching for deployment_id in all deployments in order to differentiate
    not finding the deployment then other kinds of errors, like server
    failure.
    """
    deployments = client.deployments.list(_include=['id'], id=deployment_id)
    return deployments[0] if deployments else None


def get_desired_operation_input(key, args):
    """ Resolving a key's value from kwargs or
    runtime properties, node properties in the order of priority.
    """
    return (args.get(key) or
            ctx.instance.runtime_properties.get(key) or
            ctx.node.properties.get(key))


def get_client(kwargs):
    client_config = get_desired_operation_input('client', kwargs)
    if client_config:
        client = CloudifyClient(**client_config)

        # for determining an external client:
        manager_ips = {}
        for mgr in manager.get_rest_client().manager.get_managers():
            manager_ips |= {mgr.private_ip, mgr.public_ip}
        internal_hosts = ({'127.0.0.1', 'localhost'} | manager_ips)
        host = {client.host} if isinstance(client.host, str) \
            else set(client.host)
        is_external_host = not (host & internal_hosts)
        if host - internal_hosts:
            ctx.logger.warning(
                'Only partial match between the destination client host and '
                'the local manager: the following IPs are external: %s. '
                'Treating as local client.', list(host - internal_hosts))
    else:
        client = manager.get_rest_client()
        is_external_host = False
    return client, is_external_host


def get_idd(deployment_id, is_external_host, dependency_type, kwargs):
    inter_deployment_dependency = create_deployment_dependency(
        dependency_creator_generator(dependency_type, ctx.instance.id),
        source_deployment=ctx.deployment.id,
        target_deployment=deployment_id
    )
    local_dependency = None
    if is_external_host:
        client_config = get_desired_operation_input('client', kwargs)
        manager_ips = {}
        for mgr in manager.get_rest_client().manager.get_managers():
            manager_ips |= {mgr.public_ip}
        local_dependency = create_deployment_dependency(
            dependency_creator_generator(dependency_type, ctx.instance.id),
            source_deployment=ctx.deployment.id,
            target_deployment=' ',
            external_target={
                'deployment': deployment_id,
                'client_config': client_config
            },
        )
        inter_deployment_dependency['external_source'] = {
            'deployment': ctx.deployment.id,
            'tenant': ctx.tenant_name,
            'host': list(manager_ips)
        }
    return inter_deployment_dependency, local_dependency

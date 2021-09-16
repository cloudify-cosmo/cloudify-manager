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

from cloudify import manager, ctx
from cloudify.decorators import operation
from cloudify._compat import urlparse
from cloudify.exceptions import NonRecoverableError, OperationRetry
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    ForbiddenWhileCancelling,
)

from cloudify_types.utils import proxy_operation

from .component import Component
from .polling import (
    poll_with_timeout,
    is_all_executions_finished,
    verify_execution_state,
    wait_for_blueprint_to_upload
)
from .constants import (
    DEPLOYMENTS_CREATE_RETRIES,
    EXECUTIONS_TIMEOUT,
    POLLING_INTERVAL,
    EXTERNAL_RESOURCE
)
from .utils import (
    blueprint_id_exists,
    deployment_id_exists,
    update_runtime_properties,
)


def _is_valid_url(candidate):
    parse_url = urlparse(candidate)
    return not (parse_url.netloc and parse_url.scheme)


def _get_desired_operation_input(key, args):
    """ Resolving a key's value from kwargs or
    runtime properties, node properties in the order of priority.
    """
    return (args.get(key) or
            ctx.instance.runtime_properties.get(key) or
            ctx.node.properties.get(key))


@operation(resumable=True)
def upload_blueprint(ctx, **kwargs):
    resource_config = _get_desired_operation_input('resource_config', kwargs)
    client_config = _get_desired_operation_input('client', kwargs)
    if client_config:
        client = CloudifyClient(**client_config)
    else:
        client = manager.get_rest_client()

    blueprint = resource_config.get('blueprint', {})
    blueprint_id = blueprint.get('id') or ctx.instance.id
    blueprint_archive = blueprint.get('blueprint_archive')
    blueprint_file_name = blueprint.get('main_file_name')

    if 'blueprint' not in ctx.instance.runtime_properties:
        ctx.instance.runtime_properties['blueprint'] = dict()

    update_runtime_properties('blueprint', 'id', blueprint_id)
    update_runtime_properties(
        'blueprint', 'blueprint_archive', blueprint_archive)
    update_runtime_properties(
        'blueprint', 'application_file_name', blueprint_file_name)

    blueprint_exists = blueprint_id_exists(client, blueprint_id)

    if blueprint.get(EXTERNAL_RESOURCE) and not blueprint_exists:
        raise NonRecoverableError(
            'Blueprint ID \"{0}\" does not exist, '
            'but {1} is {2}.'.format(
                blueprint_id,
                EXTERNAL_RESOURCE,
                blueprint.get(EXTERNAL_RESOURCE)))
    elif blueprint.get(EXTERNAL_RESOURCE) and blueprint_exists:
        ctx.logger.info("Using external blueprint.")
        return True
    elif blueprint_exists:
        ctx.logger.info(
            'Blueprint ID "{0}" exists, '
            'but {1} is {2}, will use the existing one.'.format(
                blueprint_id,
                EXTERNAL_RESOURCE,
                blueprint.get(EXTERNAL_RESOURCE)))
        return True
    if not blueprint_archive:
        raise NonRecoverableError(
            'No blueprint_archive supplied, '
            'but {0} is False'.format(EXTERNAL_RESOURCE))

    # Check if the ``blueprint_archive`` is not a URL then we need to
    # download it and pass the binaries to the client_args
    if _is_valid_url(blueprint_archive):
        blueprint_archive = ctx.download_resource(blueprint_archive)

    try:
        client.blueprints._upload(
            blueprint_id=blueprint_id,
            archive_location=blueprint_archive,
            application_file_name=blueprint_file_name)
        wait_for_blueprint_to_upload(blueprint_id, client)
    except CloudifyClientError as ex:
        if 'already exists' not in str(ex):
            raise NonRecoverableError(
                'Client action "_upload" failed: {0}.'.format(ex))
    return True


@operation(resumable=True)
@proxy_operation('create_deployment')
def create(operation, **_):
    return getattr(Component(_), operation)()


@operation(resumable=True)
@proxy_operation('delete_deployment')
def delete(operation, **_):
    return getattr(Component(_), operation)()


@operation(resumable=True)
@proxy_operation('execute_workflow')
def execute_start(operation, **_):
    return getattr(Component(_), operation)()

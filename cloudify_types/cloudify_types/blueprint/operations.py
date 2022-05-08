import os
import json
from cloudify import ctx
from cloudify.decorators import operation
from cloudify._compat import urlparse
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_types.utils import (errors_nonrecoverable,
                                  get_desired_operation_input,
                                  get_client)

from ..component.operations import (
    validate_labels,
    _set_secrets,
    _upload_plugins,
    _delete_plugins,
    _delete_secrets
)
from ..component.utils import blueprint_id_exists
from ..component.constants import EXTERNAL_RESOURCE
from ..component.polling import wait_for_blueprint_to_upload


def _is_internal_path(candidate):
    parse_url = urlparse(candidate)
    return not (parse_url.netloc and parse_url.scheme)


@operation(resumable=True)
@errors_nonrecoverable
def upload(**kwargs):
    blueprint = get_desired_operation_input('resource_config', kwargs)
    client, is_external_host = get_client(kwargs)

    blueprint_id = blueprint.get('id') or ctx.instance.id
    blueprint_archive = blueprint.get('blueprint_archive')
    blueprint_file_name = blueprint.get('main_file_name')
    labels = blueprint.get('labels', [])

    ctx.instance.runtime_properties['id'] = blueprint_id
    ctx.instance.runtime_properties['blueprint_archive'] = blueprint_archive
    ctx.instance.runtime_properties['application_file_name'] = \
        blueprint_file_name
    ctx.instance.runtime_properties['labels'] = labels
    blueprint_exists = blueprint_id_exists(client, blueprint_id)

    if blueprint.get(EXTERNAL_RESOURCE) and not blueprint_exists:
        raise NonRecoverableError(
            f'Blueprint ID "{blueprint_id}" does not exist '
            f'on tenant "{ctx.tenant_name}", but {EXTERNAL_RESOURCE} '
            f'is {blueprint.get(EXTERNAL_RESOURCE)}.'
        )
    elif blueprint.get(EXTERNAL_RESOURCE) and blueprint_exists:
        ctx.logger.info("Using external blueprint.")

    elif blueprint_exists:
        raise NonRecoverableError('Blueprint "%s" already exists on host %s',
                                  blueprint_id, client.host)
    if not blueprint_archive:
        raise NonRecoverableError('No blueprint_archive supplied')
    if not validate_labels(labels):
        raise NonRecoverableError(
            "The provided labels are not valid. "
            "Labels must be a list of single-entry dicts, "
            "e.g. [{\'foo\': \'bar\'}]. "
            "This value was provided: %s." % labels
        )
    # set secrets and plugins
    secrets = get_desired_operation_input('secrets', kwargs)
    _set_secrets(client, secrets)
    plugins = get_desired_operation_input('plugins', kwargs)
    _upload_plugins(client, plugins)

    if blueprint.get(EXTERNAL_RESOURCE):
        return True

    # If the ``blueprint_archive`` is not a URL then we need to download
    # it from within the main blueprint in the file-server and pass the
    # binaries to the client_args
    is_directory = False
    if _is_internal_path(blueprint_archive):
        try:
            res = ctx.get_resource(blueprint_archive)
            assert 'files' in json.loads(res)
            is_directory = True
            blueprint_archive = ctx.download_directory(blueprint_archive)
        except (ValueError, AssertionError):
            # blueprint_archive path is not a directory -> proceed normally
            blueprint_archive = ctx.download_resource(blueprint_archive)

    try:
        if is_directory:
            client.blueprints.upload(
                entity_id=blueprint_id,
                path=os.path.join(blueprint_archive, blueprint_file_name),
                labels=labels,
                skip_size_limit=True)
        else:
            client.blueprints._upload(
                blueprint_id=blueprint_id,
                archive_location=blueprint_archive,
                application_file_name=blueprint_file_name,
                labels=labels)
        wait_for_blueprint_to_upload(blueprint_id, client)
    except CloudifyClientError as ex:
        if 'already exists' not in str(ex):
            raise NonRecoverableError(
                f'Client action "_upload" failed: {ex}.')
    return True


def _delete_runtime_properties():
    for property_name in ['id', 'blueprint_archive', 'blueprint_name',
                          'labels']:
        if property_name in ctx.instance.runtime_properties:
            del ctx.instance.runtime_properties[property_name]


@operation(resumable=True)
@errors_nonrecoverable
def delete(**kwargs):
    client, is_external_host = get_client(kwargs)
    blueprint = get_desired_operation_input('resource_config', kwargs)
    blueprint_id = blueprint.get('id') or ctx.instance.id
    blueprint_exists = blueprint_id_exists(client, blueprint_id)
    if not blueprint.get(EXTERNAL_RESOURCE):
        if blueprint_exists:
            ctx.logger.info('Deleting blueprint "%s" from host %s',
                            blueprint_id, client.host)
            client.blueprints.delete(blueprint_id=blueprint_id)
        else:
            ctx.logger.warning('Blueprint "%s" was already deleted from '
                               'host %s. Skipping.', blueprint_id, client.host)

    _delete_plugins(client)
    _delete_secrets(client, get_desired_operation_input('secrets', kwargs))
    _delete_runtime_properties()
    return True

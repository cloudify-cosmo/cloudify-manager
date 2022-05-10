from cloudify import ctx
from cloudify.decorators import operation
from cloudify_types.utils import (do_upload_blueprint,
                                  upload_secrets_and_plugins,
                                  delete_plugins_secrets_and_runtime,
                                  errors_nonrecoverable,
                                  get_desired_operation_input,
                                  blueprint_id_exists,
                                  get_client)

from ..component.constants import EXTERNAL_RESOURCE


@operation(resumable=True)
@errors_nonrecoverable
def upload(**kwargs):
    blueprint = get_desired_operation_input('resource_config', kwargs)
    client, is_external_host = get_client(kwargs)
    do_upload_blueprint(client, blueprint)
    upload_secrets_and_plugins(client, kwargs)
    return True


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

    delete_plugins_secrets_and_runtime(
        client,
        get_desired_operation_input('secrets', kwargs),
        ['id', 'blueprint_archive', 'blueprint_name', 'labels']
    )
    return True

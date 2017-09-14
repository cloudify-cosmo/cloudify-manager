
import yaml

from sqlalchemy.orm.attributes import flag_modified

from .. import acfy, exceptions
from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import PROVIDER_CONTEXT_ID
from manager_rest.storage import get_storage_manager, models


@acfy.group(name='context')
def context():
    setup_flask_app()


def _merge_dicts(d, added):
    for k, v in added.items():
        if isinstance(v, dict):
            _merge_dicts(d.setdefault(k, {}), v)
        else:
            d[k] = v


@context.command(name='get')
@acfy.options.with_manager_deployment
@acfy.pass_logger
def get_context(with_manager_deployment, logger):
    sm = get_storage_manager()
    ctx = sm.get(models.ProviderContext, PROVIDER_CONTEXT_ID)
    context = ctx.context

    if not with_manager_deployment:
        context['cloudify']['manager_deployment'] = '[omitted]'
    logger.info(yaml.safe_dump(context))


@context.command(name='update')
@acfy.options.parameters
@acfy.pass_logger
def update_context(parameters, logger):
    sm = get_storage_manager()
    ctx = sm.get(models.ProviderContext, PROVIDER_CONTEXT_ID)

    if not isinstance(parameters, dict):
        raise exceptions.CloudifyACliError('Parameters must be a dict')
    _merge_dicts(ctx.context, parameters)
    flag_modified(ctx, 'context')
    sm.update(ctx)

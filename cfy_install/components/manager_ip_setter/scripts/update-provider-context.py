import sys
from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage import get_storage_manager, models
from manager_rest.constants import PROVIDER_CONTEXT_ID
from sqlalchemy.orm.attributes import flag_modified


def update_provider_context(manager_ip):
    with setup_flask_app().app_context():
        sm = get_storage_manager()
        ctx = sm.get(models.ProviderContext, PROVIDER_CONTEXT_ID)
        agent_dict = ctx.context['cloudify']['cloudify_agent']
        agent_dict['broker_ip'] = manager_ip
        agent_dict['networks']['default'] = manager_ip
        flag_modified(ctx, 'context')
        sm.update(ctx)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Expected 1 argument - <manager-ip>')
        print('Provided args: {0}'.format(sys.argv[1:]))
        sys.exit(1)
    update_provider_context(sys.argv[1])

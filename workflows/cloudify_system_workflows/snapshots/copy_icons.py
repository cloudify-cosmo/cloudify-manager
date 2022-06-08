import os
import sys
import shutil

from manager_rest.flask_utils import setup_flask_app
from manager_rest import config
from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    BLUEPRINT_ICON_FILENAME)

STAGE_ICONS_PATH = '/opt/cloudify-stage/dist/userData/blueprint-icons'


def load_icons():
    if not os.path.exists(STAGE_ICONS_PATH):
        sys.stderr.write('No stage icons found, aborting icon copy.\n')
        return

    with setup_flask_app().app_context():
        config.instance.load_configuration()
        fs_blueprints_path = os.path.join(config.instance.file_server_root,
                                          FILE_SERVER_BLUEPRINTS_FOLDER)
    existing_blueprints = {}
    for tenant in os.listdir(fs_blueprints_path):
        tenant_path = os.path.join(fs_blueprints_path, tenant)
        for blueprint in os.listdir(tenant_path):
            existing_blueprints.setdefault(blueprint, []).append(tenant)

    icon_blueprints = os.listdir(STAGE_ICONS_PATH)

    for blueprint in icon_blueprints:
        icon_path = os.path.join(STAGE_ICONS_PATH, blueprint, 'icon.png')
        if blueprint in existing_blueprints:
            for tenant in existing_blueprints[blueprint]:
                dest_path = os.path.join(fs_blueprints_path,
                                         tenant,
                                         blueprint,
                                         BLUEPRINT_ICON_FILENAME)
                shutil.copy(icon_path, dest_path)
            # We're not deleting because of file ownership issues,
            # but even a relatively large amount of icons will not
            # be absolutely massive in size so this shouldn't be a
            # massive problem (and it'll only apply if icons are
            # heavily used, and only on the manager doing the
            # upgrade).
        else:
            sys.stderr.write(
                f'Found icon for blueprints named {blueprint}, but no '
                f'blueprints of that name. Icon is in {icon_path}\n')


if __name__ == '__main__':
    if 'MANAGER_REST_CONFIG_PATH' not in os.environ:
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            "/opt/manager/cloudify-rest.conf"
    load_icons()

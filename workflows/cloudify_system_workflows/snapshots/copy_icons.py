import os
import sys
import shutil

from manager_rest.constants import (FILE_SERVER_ROOT,
                                    FILE_SERVER_BLUEPRINTS_FOLDER,
                                    BLUEPRINT_ICON_FILENAME)

STAGE_ICONS_PATH = '/opt/cloudify-stage/dist/userData/blueprint-icons'
FS_BLUEPRINTS_PATH = os.path.join(FILE_SERVER_ROOT,
                                  FILE_SERVER_BLUEPRINTS_FOLDER)


def load_icons():
    if not os.path.exists(STAGE_ICONS_PATH):
        sys.stderr.write('No stage icons found, aborting icon copy.\n')
        return

    existing_blueprints = {}
    for tenant in os.listdir(FS_BLUEPRINTS_PATH):
        tenant_path = os.path.join(FS_BLUEPRINTS_PATH, tenant)
        if not os.isdir(tenant_path):
            continue
        for blueprint in os.listdir(tenant_path):
            blueprint_path = os.path.join(tenant_path, blueprint)
            if not os.isdir(blueprint_path):
                continue
            existing_blueprints.setdefault(blueprint, []).append(tenant)

    icon_blueprints = os.listdir(STAGE_ICONS_PATH)

    for blueprint in icon_blueprints:
        icon_path = os.path.join(STAGE_ICONS_PATH, blueprint, 'icon.png')
        if blueprint in existing_blueprints:
            for tenant in existing_blueprints[blueprint]:
                dest_path = os.path.join(FS_BLUEPRINTS_PATH,
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
    load_icons()

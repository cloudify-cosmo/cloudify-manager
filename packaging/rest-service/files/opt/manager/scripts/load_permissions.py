#!/opt/manager/env/bin/python

import argparse
import os
import sys

import yaml

from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage import models
from manager_rest.storage.models_base import db


def load_permissions(authorization_file_path, debug=False):

    with open(authorization_file_path) as f:
        auth_data = yaml.safe_load(f)

    with setup_flask_app().app_context():
        db.session.execute("SET SESSION audit.execution_id = :id",
                           params={'id': 'load_permissions'})
        existing_roles = db.session.query(models.Role)
        existing_role_names = [
            role.name for role in existing_roles
        ]
        new_roles = {role['name']: role for role in auth_data['roles']}
        for role in existing_roles:
            if role.name in new_roles:
                role.type = new_roles[role.name]['type']
                role.description = new_roles[role.name]['description']
        for role_name, role in new_roles.items():
            if role_name not in existing_role_names:
                db.session.add(models.Role(
                    name=role['name'],
                    type=role['type'],
                    description=role['description']
                ))
        roles = {r.name: r.id for r in
                 db.session.query(models.Role.name, models.Role.id)}
        existing_permissions = [
            (perm.role_id, perm.name)
            for perm in db.session.query(models.Permission)
        ]
        for permission, permission_roles in auth_data['permissions'].items():
            for role_name in permission_roles:
                if role_name not in roles:
                    sys.stderr.write(
                        'Could not add permission {perm} for role {role} as '
                        'role does not exist.\n'.format(
                            perm=permission,
                            role=role_name,
                        )
                    )
                    continue
                if (roles[role_name], permission) in existing_permissions:
                    if debug:
                        print(
                            'Permission {perm} for role {role} already '
                            'exists.'.format(perm=permission, role=role_name)
                        )
                    continue
                db.session.add(models.Permission(
                    role_id=roles[role_name],
                    name=permission
                ))
        db.session.commit()


if __name__ == '__main__':
    if 'MANAGER_REST_CONFIG_PATH' not in os.environ:
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            "/opt/manager/cloudify-rest.conf"
    parser = argparse.ArgumentParser(
        description="Load roles and permissions defined in an "
                    "authorization.conf file into the database")
    parser.add_argument(
        '--authorization_file_path', '-a',
        help="Path to file containing roles and permissions to be imported.",
        default='/opt/manager/authorization.conf',
    )
    parser.add_argument(
        '--debug', '-d',
        help="Whether to include debug output.",
        default=False,
        action='store_true',
    )
    args = parser.parse_args()
    load_permissions(args.authorization_file_path, args.debug)

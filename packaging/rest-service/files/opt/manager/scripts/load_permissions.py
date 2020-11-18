#!/opt/manager/env/bin/python

import argparse
import os
import yaml

from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage import models
from manager_rest.storage.models_base import db


def load_permissions(authorization_file_path):

    with open(authorization_file_path) as f:
        auth_data = yaml.safe_load(f)

    with setup_flask_app():
        for role in auth_data['roles']:
            db.session.add(models.Role(
                name=role['name'],
                type=role['type'],
                description=role['description']
            ))
        roles = {r.name: r.id for r in
                 db.session.query(models.Role.name, models.Role.id)}
        for permission, permission_roles in auth_data['permissions'].items():
            for role_name in permission_roles:
                if role_name not in roles:
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
        'authorization_file_path', default='/opt/manager/authorization.conf')
    args = parser.parse_args()
    load_permissions(args.authorization_file_path)

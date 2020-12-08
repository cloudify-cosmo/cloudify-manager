import argparse
import logging
import os

import yaml

from manager_rest import config
from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage.models_base import db


def _update_roles(new_roles, keep):
    existing_roles = {r.name: r for r in
                      db.session.execute('select id, type, name from roles')}
    logging.info('Found %d existing roles', len(existing_roles))
    logging.debug('Found roles: %s', existing_roles)
    new_roles = {r['name']: r for r in new_roles}
    roles_to_drop = set(existing_roles) - set(new_roles)
    roles_to_add = set(new_roles) - set(existing_roles)
    for role in roles_to_add:
        db.session.execute(
            'insert into roles(name, type, description) '
            'values (:name, :type, :description)',
            {
                'name': role['name'],
                'description': role.get('description'),
                'type': role.get('type', 'system_role')
            }
        )
    logging.debug('Added roles: %s', roles_to_add)
    logging.info('Inserted %d new roles', len(roles_to_add))
    if keep:
        logging.debug('Not dropping roles!')
    else:
        for r in roles_to_drop:
            db.session.execute('delete from roles where id=:id', {'id': r.id})
        logging.info('Deleted %d old roles', len(roles_to_drop))
        logging.debug('Dropping roles: %s', roles_to_drop)


def _update_permissions(new_permissions, keep):
    if keep:
        logging.debug('Not dropping permissions!')
    else:
        count = db.session.execute('delete from permissions')
        logging.info('Deleted %d old permissions', count.rowcount)

    roles = {r.name: r for r in
             db.session.execute('select id, name from roles')}

    inserted = 0
    for permission, perm_roles in new_permissions.items():
        for role_name in perm_roles:
            if role_name not in roles:
                logging.warning(
                    'Not inserting %s for nonexistent role %s',
                    permission, role_name)
                continue
            inserted += 1
            logging.debug('Inserting %s for %s', permission, role_name)
            db.session.execute(
                'insert into permissions(role_id, name) '
                'values (:roleid, :name)',
                {'roleid': roles[role_name].id, 'name': permission})
    logging.info('Inserted %d permissions', inserted)


def main(source, replace, commit):

    with open(source) as f:
        data = yaml.safe_load(f)

    _update_roles(data['roles'], replace)
    _update_permissions(data['permissions'], replace)
    if commit:
        db.session.commit()


if __name__ == '__main__':
    os.environ.setdefault('MANAGER_REST_CONFIG_PATH',
                          '/opt/manager/cloudify-rest.conf')
    parser = argparse.ArgumentParser(
        description='Insert permissions from an authorization.conf file')
    parser.add_argument('--source', default='/opt/manager/authorization.conf',
                        help='The file to load permissions from')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    parser.add_argument('--keep', action='store_true',
                        help='Keep pre-existing roles and permissions '
                        '(replaces otherwise)')
    parser.add_argument('--commit', action='store_true',
                        help='Commit changes, otherwise dry-run')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(levelname)s %(asctime)s %(message)s')
    config.instance.load_configuration()

    app = setup_flask_app()

    if args.verbose > 1:
        app.config['SQLALCHEMY_ECHO'] = True
        sqla_lgr = logging.getLogger('sqlalchemy.engine.base.Engine')
        sqla_lgr.addHandler(logging.NullHandler())

    with app.app_context():
        main(args.source, args.keep, args.commit)

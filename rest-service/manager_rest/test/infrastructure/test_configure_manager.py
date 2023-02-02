from copy import deepcopy
from datetime import datetime
from unittest import mock

from sqlalchemy import select

from manager_rest import config, constants, permissions
from manager_rest.configure_manager import (
    configure,
    dict_merge,
    _load_user_config,
)
from manager_rest.storage import db, models
from manager_rest.test import base_test


BASIC_CONFIG = {
    'agent': {
        'broker_port': 5671,
        'heartbeat': 30,
        'log_level': 'INFO',
        'max_workers': 2,
        'min_workers': 1,
    },
    'manager': {
        'public_ip': 'example.com',
    },
    'mgmtworker': {
        'max_workers': 2,
        'min_workers': 1,
        'workflows': {},
    },
    'restservice': {
        'account_lock_period': 1,
        'default_page_size': 100,
        'failed_logins_before_account_lock': 1,
        'insecure_endpoints_disabled': False,
        'log': {
            'level': 'INFO',
        },
        'min_available_memory_mb': 1,
    },
}


def user_config(cfg: dict):
    updated_config = deepcopy(BASIC_CONFIG)
    dict_merge(updated_config, cfg)
    return updated_config


def test_dict_merge():
    assert dict_merge({}, {}) == {}
    assert dict_merge({}, {1: 2}) == {1: 2}
    assert dict_merge({1: 2}, {}) == {1: 2}
    assert dict_merge({1: 2}, {3: 4}) == {1: 2, 3: 4}
    assert dict_merge({1: 2}, {1: 3}) == {1: 3}
    assert dict_merge({1: {2: 3}}, {1: {3: 4}}) == {1: {2: 3, 3: 4}}
    assert dict_merge({1: {2: 3}}, {1: {2: 4}}) == {1: {2: 4}}
    assert dict_merge({1: {2: {3: 4}}}, {1: {2: {3: 5}}}) == {1: {2: {3: 5}}}


def test_load_user_config(tmpdir):
    conf1 = tmpdir / 'conf1.yaml'
    conf2 = tmpdir / 'conf2.yaml'
    conf1.write_text('a: 1\nb: 2', encoding='utf-8')
    conf2.write_text('a: 1\nb: 3', encoding='utf-8')
    loaded = _load_user_config([
        str(conf1),
        str(conf2),
        None,
    ])
    assert loaded == {
        'a': 1,
        'b': 3,
    }


class TestConfigureManager(base_test.BaseServerTestCase):
    def test_create_admin(self):
        # delete the admin user first
        db.session.delete(self.user)
        assert models.User.query.count() == 0
        # empty config, so the username & password will be defaulted
        configure(BASIC_CONFIG)
        assert models.User.query.count() == 1

    def test_create_admin_username(self):
        db.session.delete(self.user)
        assert models.User.query.count() == 0
        configure(user_config({
            'manager': {
                'security': {
                    'admin_username': 'admin2',
                }
            }
        }))
        assert models.User.query.count() == 1
        models.User.query.filter_by(username='admin2').one()  # doesn't throw

    def test_update_admin_password(self):
        assert models.User.query.count() == 1
        original_password = models.User.query.one().password
        configure(user_config({
            'manager': {
                'security': {
                    'admin_password': 'abcdefgh',
                }
            }
        }))
        assert original_password != models.User.query.one().password

    def test_create_default_tenant(self):
        db.session.delete(self.tenant)
        assert self.user.tenant_associations == []

        configure(BASIC_CONFIG)
        assert models.Tenant.query.count() == 1
        assert len(self.user.tenant_associations) == 1

    def test_register_rabbitmq_brokers(self):
        models.RabbitMQBroker.query.delete()
        # after deleting the brokers and reloading config, rabbitmq data
        # is unavailable
        config.instance.load_from_db()
        assert not config.instance.amqp_host

        configure(user_config({
            'rabbitmq': {
                'username': 'username1',
                'password': 'password1',
                'cluster_members': {
                    'test_hostname_1': {
                        'networks': {
                            'default': 'test_address_1',
                        },
                    },
                    'test_hostname_2': {
                        'networks': {
                            'default': 'test_address_2',
                        },
                    },
                },
            },
        }))

        test_hostname_1 = models.RabbitMQBroker.query.filter_by(
            name='test_hostname_1',
        ).one()
        test_hostname_2 = models.RabbitMQBroker.query.filter_by(
            name='test_hostname_2',
        ).one()

        assert models.RabbitMQBroker.query.count() == 2
        assert test_hostname_1.management_host == 'test_address_1'
        assert test_hostname_2.management_host == 'test_address_2'

        # rabbitmq data is loaded into config after the configure() call
        # directly, without calling .load_from_db() here
        assert config.instance.amqp_host
        assert config.instance.amqp_username == 'username1'
        assert config.instance.amqp_password == 'password1'

    def test_create_roles(self):
        db.session.execute(models.Role.__table__.delete())
        assert len(models.Role.query.all()) == 0

        configure(user_config({
            'roles': [
                {
                    'name': 'role1'
                },
                {
                    'name': 'role2',
                    'type': 'tenant_role',
                    'description': 'descr1',
                },
            ]
        }))

        # in the created roles, we expect the ones from the config...
        expected_roles = {
            ('role1', 'system_role', None),
            ('role2', 'tenant_role', 'descr1'),
        }
        # ...and also the default roles as well
        for default_role in permissions.ROLES:
            expected_roles.add((
                default_role['name'],
                default_role['type'],
                default_role['description'],
            ))
        roles = {
            (r.name, r.type, r.description)
            for r in models.Role.query.all()
        }

        assert roles == expected_roles

    def test_create_roles_override(self):
        db.session.execute(models.Role.__table__.delete())
        assert len(models.Role.query.all()) == 0

        # creating roles that are also default roles, still overrides their
        # description
        configure(user_config({
            'roles': [
                {
                    'name': 'sys_admin',
                    'description': 'descr',
                },
                {
                    'name': constants.DEFAULT_TENANT_ROLE,
                    'description': 'descr',
                },
            ]
        }))
        roles = models.Role.query.all()
        assert len(roles) == 2
        assert all(r.description == 'descr' for r in roles)

        # ...doing it again, updates them
        configure(user_config({
            'roles': [
                {
                    'name': 'sys_admin',
                    'description': 'descr2',
                },
                {
                    'name': constants.DEFAULT_TENANT_ROLE,
                    'description': 'descr2',
                },
            ]
        }))

        assert len(roles) == 2
        assert all(r.description == 'descr2' for r in roles)

    def test_create_permissions(self):
        db.session.execute(models.Permission.__table__.delete())
        assert len(models.Permission.query.all()) == 0
        configure(BASIC_CONFIG)

        created_permissions = models.Permission.query.all()
        assert len(created_permissions) == len(permissions.PERMISSIONS)

    def test_create_permissions_set_user(self):
        db.session.execute(models.Permission.__table__.delete())
        assert len(models.Permission.query.all()) == 0
        configure(user_config({
            'permissions': {
                # you tried to deny sys_admin some of their permissions?
                # fat chance, they'll get it anyway!
                'user_get': ['user']
            },
        }))

        created_permissions = models.Permission.query.all()
        # +1 because we created 1 additional permission: user_get for role=user
        assert len(created_permissions) == len(permissions.PERMISSIONS) + 1
        user_get_permissions = (
            models.Permission.query
            .filter_by(name='user_get')
            .all()
        )
        assert len(user_get_permissions) == 2
        assert {p.role_name for p in user_get_permissions} == \
            {'user', 'sys_admin'}

    def test_create_permissions_nonexistent_role(self):
        with self.assertRaisesRegex(ValueError, 'something.*nonexistent'):
            configure(user_config({
                'permissions': {
                    'something': ['nonexistent role']
                },
            }))

    def test_insert_manager_cert_config(self):
        assert len(models.Manager.query.all()) == 0
        configure(user_config({
            'manager': {
                'hostname': 'mgr1',
                'private_ip': 'example.com',
                'public_ip': 'example.com',
                'ca_cert': 'cert-content-1',
            },
        }))
        assert len(models.Manager.query.all()) == 1
        mgr = models.Manager.query.first()
        assert mgr.hostname == 'mgr1'
        assert mgr.ca_cert
        assert mgr.ca_cert.value == 'cert-content-1'

    def test_insert_manager_cert_file(self):
        assert len(models.Manager.query.all()) == 0
        with mock.patch(
            'manager_rest.configure_manager.open',
            mock.mock_open(read_data='cert-content-1'),
        ):
            configure(user_config({
                'manager': {
                    'hostname': 'mgr1',
                    'private_ip': 'example.com',
                    'public_ip': 'example.com',
                },
            }))
        assert len(models.Manager.query.all()) == 1
        mgr = models.Manager.query.first()
        assert mgr.hostname == 'mgr1'
        assert mgr.ca_cert
        assert mgr.ca_cert.value == 'cert-content-1'

    def test_insert_manager_cert_missing(self):
        assert len(models.Manager.query.all()) == 0
        with mock.patch(
            'manager_rest.configure_manager.open',
            mock.mock_open(read_data=''),
        ):
            with self.assertRaisesRegex(RuntimeError, 'ca_cert'):
                configure(user_config({
                    'manager': {
                        'hostname': 'mgr1',
                        'private_ip': 'example.com',
                        'public_ip': 'example.com',
                    },
                }))

    def test_update_manager(self):
        assert len(models.Manager.query.all()) == 0
        mgr = models.Manager(
            hostname='mgr1',
            private_ip='example.com',
            public_ip='example.com',
            version='7.0.0',
            edition='premium',
            distribution='fake',
            distro_release='fake',
            last_seen=datetime.utcnow(),
            ca_cert=models.Certificate(name='mgr1-ca', value='cert-content-1'),
        )
        db.session.add(mgr)

        configure(user_config({
            'manager': {
                'hostname': 'mgr1',
                'private_ip': 'example2.com',
            },
        }))
        assert mgr.private_ip == 'example2.com'

    def test_update_manager_cert_differs(self):
        assert len(models.Manager.query.all()) == 0
        mgr = models.Manager(
            hostname='mgr1',
            private_ip='example.com',
            public_ip='example.com',
            version='7.0.0',
            edition='premium',
            distribution='fake',
            distro_release='fake',
            last_seen=datetime.utcnow(),
            ca_cert=models.Certificate(name='mgr1-ca', value='cert-content-1'),
        )
        db.session.add(mgr)

        with self.assertRaisesRegex(RuntimeError, 'ca_cert.*differ'):
            configure(user_config({
                'manager': {
                    'hostname': 'mgr1',
                    'private_ip': 'example2.com',
                    'ca_cert': 'cert-content-2',
                },
            }))
        assert mgr.private_ip == 'example2.com'

    def test_create_config_defaults(self):
        configure(user_config({
            'manager': {
                'public_ip': 'example.org',
            },
            'mgmtworker': {
                'max_workers': 9,
            },
            'agent': {
                'heartbeat': 99
            }
        }))
        created_config = db.session.scalars(select(models.Config)).all()
        assert len(created_config) > 0

        for scope, name, value in [
            ('rest', 'public_ip', 'example.org'),
            ('rest', 'file_server_url', 'https://localhost:53333/resources'),
            ('mgmtworker', 'max_workers', 9),
            ('agent', 'heartbeat', 99),
        ]:
            inst = db.session.scalars(
                select(models.Config).filter_by(scope=scope, name=name)
            ).one()
            assert inst.value == value

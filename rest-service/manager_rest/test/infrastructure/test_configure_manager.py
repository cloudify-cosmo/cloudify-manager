from manager_rest import config, constants, permissions
from manager_rest.configure_manager import (
    configure,
    dict_merge,
    _load_user_config,
)
from manager_rest.storage import db, models
from manager_rest.test import base_test


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
        configure({})
        assert models.User.query.count() == 1

    def test_create_admin_username(self):
        db.session.delete(self.user)
        assert models.User.query.count() == 0
        configure({
            'manager': {
                'security': {
                    'admin_username': 'admin2',
                }
            }
        })
        assert models.User.query.count() == 1
        models.User.query.filter_by(username='admin2').one()  # doesn't throw

    def test_update_admin_password(self):
        assert models.User.query.count() == 1
        original_password = models.User.query.one().password

        configure({
            'manager': {
                'security': {
                    'admin_password': 'abcdefgh',
                }
            }
        })
        assert original_password != models.User.query.one().password

    def test_create_default_tenant(self):
        db.session.delete(self.tenant)
        assert self.user.tenant_associations == []

        configure({})
        assert models.Tenant.query.count() == 1
        assert len(self.user.tenant_associations) == 1

    def test_register_rabbitmq_brokers(self):
        models.RabbitMQBroker.query.delete()
        # after deleting the brokers and reloading config, rabbitmq data
        # is unavailable
        config.instance.load_from_db()
        assert not config.instance.amqp_host

        user_config = {
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
        }

        configure(user_config)

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

        configure({
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
        })

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
        configure({
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
        })
        roles = models.Role.query.all()
        assert len(roles) == 2
        assert all(r.description == 'descr' for r in roles)

        # ...doing it again, updates them
        configure({
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
        })

        assert len(roles) == 2
        assert all(r.description == 'descr2' for r in roles)

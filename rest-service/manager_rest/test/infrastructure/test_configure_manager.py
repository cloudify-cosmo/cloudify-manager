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
        original_password = models.User.query.first().password

        configure({
            'manager': {
                'security': {
                    'admin_password': 'abcdefgh',
                }
            }
        })
        assert original_password != models.User.query.first().password

    def test_create_default_tenant(self):
        db.session.delete(self.tenant)
        assert self.user.tenant_associations == []

        configure({})
        assert models.Tenant.query.count() == 1
        assert len(self.user.tenant_associations) == 1

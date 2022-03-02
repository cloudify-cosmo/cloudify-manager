import mock
import pytest

from cloudify_rest_client.exceptions import UserUnauthorizedError

from manager_rest.storage import db, models
from manager_rest.test import base_test


class TestPermissions(base_test.BaseServerTestCase):
    def test_not_admin(self):
        with mock.patch('manager_rest.utils.is_administrator',
                        return_value=False):
            with pytest.raises(UserUnauthorizedError):
                self.client.permissions.list()

    def test_get_all(self):
        permissions = self.client.permissions.list()
        assert len(permissions) == models.Permission.query.count()

    def test_get_for_role(self):
        role = models.Role.query.first()
        permissions = self.client.permissions.list(role=role.name)
        assert len(permissions) == len(role.permissions)

    def test_put(self):
        role = models.Role.query.first()
        permission_name = 'something very unique'
        self.client.permissions.add(
            role=role.name,
            permission=permission_name,
        )
        retrieved = self.client.permissions.list(role=role.name)
        assert permission_name in {p['permission'] for p in retrieved}

    def test_delete(self):
        role = models.Role.query.first()
        permission_name = 'something very unique'
        self.client.permissions.add(
            role=role.name,
            permission=permission_name,
        )
        self.client.permissions.delete(
            role=role.name,
            permission=permission_name,
        )
        retrieved = self.client.permissions.list(role=role.name)
        assert permission_name not in {p['permission'] for p in retrieved}

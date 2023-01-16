from unittest import mock

import pytest

from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    UserUnauthorizedError
)

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

    def test_put_already_existing(self):
        role = models.Role(
            name='test-role',
            type='tenant_role',
        )
        test_permission = 'test-permission'
        role.permissions.append(models.Permission(name=test_permission))
        db.session.add(role)
        with pytest.raises(CloudifyClientError) as cm:
            self.client.permissions.add(
                role=role.name,
                permission=test_permission,
            )
        assert cm.value.status_code == 409

    def test_put_two_roles(self):
        """Put the same permission for two roles.

        Let's make sure that the uniqueness check doesn't actually break
        giving two different roles the same permission!
        """
        role1, role2 = models.Role.query.limit(2)
        permission_name = 'something very unique'
        for role in role1, role2:
            self.client.permissions.add(
                role=role.name,
                permission=permission_name,
            )
        for role in role1, role2:
            retrieved = self.client.permissions.list(role=role.name)
            assert permission_name in {p['permission'] for p in retrieved}

    def test_delete_nonexistent(self):
        permission_name = 'something very unique'
        with pytest.raises(CloudifyClientError) as cm:
            self.client.permissions.delete(
                permission=permission_name,
                role='a role that surely does not exist',
            )
        assert cm.value.status_code == 404

        role = models.Role.query.first()
        with pytest.raises(CloudifyClientError) as cm:
            self.client.permissions.delete(
                permission=permission_name,
                role=role.name,
            )
        assert cm.value.status_code == 404

    def test_delete_duplicated(self):
        """In case there's duplicated permissions, still allow deleting them.

        Someone might've introduced duplicated permissions by using the
        DB directly, or maybe by using an older version of Cloudify.
        Anyway, they should have a way to clean that mess up!
        """
        permission_name = 'something very unique'
        role = models.Role.query.first()
        for _ in range(5):
            db.session.add(models.Permission(
                role=role,
                name=permission_name
            ))
        self.client.permissions.delete(
            permission=permission_name,
            role=role.name,
        )
        assert models.Permission.query.filter_by(
            role=role,
            name=permission_name
        ).count() == 0

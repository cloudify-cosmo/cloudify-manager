from datetime import datetime
from functools import wraps
from manager_rest.security import SecuredResource
from manager_rest.storage import models, get_storage_manager
from manager_rest import utils, manager_exceptions
from manager_rest.rest import rest_decorators
from manager_rest.rest.responses_v3 import PermissionResponse


def _admin_only(f):
    """Only allow f, if the current user is an admin."""
    @wraps(f)
    def _inner(*a, **kw):
        if not utils.is_administrator(tenant=None):
            raise manager_exceptions.UnauthorizedError(
                'Only admin users are permitted to edit permissions')
        return f(*a, **kw)
    return _inner


class Permissions(SecuredResource):
    @rest_decorators.marshal_with(PermissionResponse)
    @rest_decorators.paginate
    @_admin_only
    def get(self, pagination=None):
        """List all permissions, for all roles"""
        return get_storage_manager().list(
            models.Permission,
            pagination=pagination
        )


class PermissionsRole(SecuredResource):
    @rest_decorators.marshal_with(PermissionResponse)
    @rest_decorators.paginate
    @_admin_only
    def get(self, role_name, pagination=None):
        """List all permissions for the role role_name"""
        sm = get_storage_manager()
        # this will 404 if the role doesn't exist
        sm.get(models.Role, None, filters={'name': role_name})
        return sm.list(
            models.Permission,
            filters={'role_name': role_name},
            pagination=pagination
        )


class PermissionsRoleId(SecuredResource):
    @rest_decorators.marshal_with(PermissionResponse)
    @_admin_only
    def put(self, role_name, permission_name):
        """Allow role_name the permission permission_name"""
        sm = get_storage_manager()
        role = sm.get(models.Role, None, filters={'name': role_name})
        perm = models.Permission(
            role=role,
            name=permission_name
        )
        with sm.transaction():
            role.updated_at = datetime.utcnow()
            sm.put(perm)
            sm.put(role)
        return perm

    @_admin_only
    def delete(self, role_name, permission_name):
        """Disallow role_name the permission permission_name"""
        sm = get_storage_manager()
        role = sm.get(models.Role, None, filters={'name': role_name})
        perm = sm.get(models.Permission, None, filters={
            'role_name': role_name,
            'name': permission_name
        })
        with sm.transaction():
            role.updated_at = datetime.utcnow()
            sm.delete(perm)
            sm.put(role)
        return None, 204

"""This module holds the manager's role & permission specification.

Default roles and permissions that are always available on the manager
are defined here.
"""

from manager_rest import constants


ROLES = [
    {
        'name': 'sys_admin',
        'type': 'system_role',
        'description': 'User that can manage Cloudify',
    },
    {
        'name': constants.DEFAULT_TENANT_ROLE,
        'type': 'tenant_role',
        'description': 'Regular user, can perform actions on tenants resources'
    }
]

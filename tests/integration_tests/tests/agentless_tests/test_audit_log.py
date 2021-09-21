from datetime import datetime
from typing import Optional, List, Type

import pytest
from dataclasses import dataclass

from cloudify_rest_client import CloudifyClient
from integration_tests import AgentlessTestCase
from integration_tests.tests.constants import USER_ROLE
from integration_tests.tests.utils import get_resource as resource
from manager_rest.constants import DEFAULT_TENANT_ROLE

pytestmark = pytest.mark.group_rest

TSFMT = "%Y-%m-%dT%H:%M:%S.%f"


class AuditLogTest(AgentlessTestCase):

    def test_audit_log_simple(self):
        blueprint_id = 'bp'
        blueprint = self.client.blueprints.upload(
            resource('dsl/empty_blueprint.yaml'),
            entity_id=blueprint_id)
        self.client.blueprints.delete(blueprint_id)

        blueprint_upload_audit_logs = filter_logs(
            self.client.auditlog.list(
                execution_id=blueprint.upload_execution['id']),
            ref_table='blueprints')
        assert blueprint_upload_audit_logs != []

        all_audit_logs = self.client.auditlog.list()
        assert len(all_audit_logs) > len(blueprint_upload_audit_logs)
        blueprint_create_audit_logs = filter_logs(all_audit_logs,
                                                  ref_table='blueprints',
                                                  operation='create')
        assert len(blueprint_create_audit_logs) == 1
        blueprint_delete_audit_logs = filter_logs(all_audit_logs,
                                                  ref_table='blueprints',
                                                  operation='delete')
        assert len(blueprint_delete_audit_logs) == 1
        assert blueprint_create_audit_logs[0]['ref_id'] == \
               blueprint_delete_audit_logs[0]['ref_id']
        assert all([log['ref_id'] == blueprint_create_audit_logs[0]['ref_id']
                    for log in blueprint_upload_audit_logs])

    def test_audit_log_truncate(self):
        timestamp_zero = datetime.utcnow()
        blueprint_id = 'bp'
        self.client.blueprints.upload(
            resource('dsl/empty_blueprint.yaml'),
            entity_id=blueprint_id)
        timestamp_after_upload = datetime.utcnow()
        self.client.blueprints.delete(blueprint_id)
        timestamp_after_delete = datetime.utcnow()

        result = self.client.auditlog.delete(before=timestamp_zero.isoformat())
        assert result.deleted > 0
        audit_logs = filter_logs(self.client.auditlog.list(),
                                 ref_table='blueprints',
                                 operation='create')
        assert len(audit_logs) == 1
        assert datetime.strptime(
            audit_logs[0]['created_at'], TSFMT) > timestamp_zero

        result = self.client.auditlog.delete(
            before=timestamp_after_upload.isoformat())
        assert result.deleted > 0
        assert len(filter_logs(self.client.auditlog.list(),
                               ref_table='blueprints',
                               operation='create')) == 0
        audit_logs = filter_logs(self.client.auditlog.list(),
                                 ref_table='blueprints',
                                 operation='delete')
        assert len(audit_logs) == 1
        assert datetime.strptime(
            audit_logs[0]['created_at'], TSFMT) > timestamp_after_upload

        result = self.client.auditlog.delete(
            before=timestamp_after_delete.isoformat())
        assert result.deleted > 0
        audit_logs = filter_logs(self.client.auditlog.list(),
                                 ref_table='blueprints')
        assert len(audit_logs) == 0


class AuditLogMultiTenantTest(AgentlessTestCase):
    @dataclass
    class User:
        name: str
        password: str
        tenant: str
        blueprint_id: str
        client: Optional[CloudifyClient]

    users: List[Type['User']] = []

    def setUp(self):
        for n in range(2):
            user = self.User(name=f"user_{n}",
                             password=f"password_{n}",
                             tenant=f"tenant_{n}",
                             blueprint_id=f"bp{n}",
                             client=None)
            self.client.users.create(user.name, user.password, USER_ROLE)
            self.client.tenants.create(user.tenant)
            self.client.tenants.add_user(user.name, user.tenant,
                                         DEFAULT_TENANT_ROLE)
            user.client = self.create_rest_client(username=user.name,
                                                  password=user.password,
                                                  tenant=user.tenant)
            self.users.append(user)

    def test_audit_log_simple(self):
        blueprint_path = resource('dsl/empty_blueprint.yaml')
        self.users[0].client.blueprints.upload(blueprint_path,
                                               self.users[0].blueprint_id)
        self.users[1].client.blueprints.upload(blueprint_path,
                                               self.users[1].blueprint_id)
        self.users[0].client.blueprints.delete(self.users[0].blueprint_id)
        self.users[1].client.blueprints.delete(self.users[1].blueprint_id)

        all_audit_logs = self.client.auditlog.list().items
        user_0_audit_logs = self.client.auditlog.list(
            creator_name=self.users[0].name).items
        user_1_audit_logs = self.client.auditlog.list(
            creator_name=self.users[1].name).items
        assert len(all_audit_logs) != []
        assert len(user_0_audit_logs) < len(all_audit_logs)
        assert len(user_1_audit_logs) < len(all_audit_logs)
        assert len(user_0_audit_logs) == len(user_1_audit_logs)
        assert set((log['ref_table'], log['ref_id'])
                   for log in user_0_audit_logs)\
            .isdisjoint(set((log['ref_table'], log['ref_id'])
                            for log in user_1_audit_logs))


def filter_logs(logs: List[dict], **kwargs) -> List[dict]:
    result = []
    for log in logs:
        match = True
        for k, v in kwargs.items():
            if k not in log or log[k] != v:
                match = False
                break
        if match:
            result.append(log)
    return result

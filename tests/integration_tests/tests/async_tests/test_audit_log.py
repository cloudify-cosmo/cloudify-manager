import asyncio
import json
from typing import List, Sequence

import aiohttp
import pytest

from cloudify_rest_client import CloudifyClient
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_api


@pytest.mark.asyncio
async def test_audit_log_stream_rest_client(
        rest_client: CloudifyClient):
    response = await rest_client.auditlog.stream(timeout=30)
    assert response.status == 200
    assert response.headers.get('Content-Type') == 'text/event-stream'

    blueprint = _upload_blueprint(rest_client)
    rest_client.blueprints.delete(blueprint.id)

    audit_logs = []
    try:
        async for data, _ in response.content.iter_chunks():
            for audit_log in _streamed_audit_log(data):
                audit_logs.append(audit_log)
                if audit_log['ref_table'] == 'blueprints' \
                        and audit_log['operation'] == 'delete':
                    response.close()
                    break
    except (asyncio.TimeoutError, aiohttp.ClientConnectionError):
        pass

    bp_create_logs = _filter_logs(
            audit_logs,
            ref_table='blueprints',
            operation='create',
    )
    assert len(bp_create_logs) == 1
    bp_create_ref_identifier = bp_create_logs[0]['ref_identifier']
    assert bp_create_ref_identifier['id'] == 'bp'
    assert bp_create_ref_identifier['tenant_id'] == 0
    assert bp_create_ref_identifier['tenant_name'] == 'default_tenant'
    assert len(_filter_logs(
        audit_logs, ref_table='blueprints', operation='delete')) == 1
    assert len(_filter_logs(
        audit_logs, execution_id=blueprint.upload_execution['id'])) >= 1


@pytest.mark.asyncio
async def test_audit_log_stream_timeout(
        rest_client: CloudifyClient):
    response = await rest_client.auditlog.stream(timeout=1)

    blueprint = _upload_blueprint(rest_client)
    rest_client.blueprints.delete(blueprint.id)

    audit_logs = []
    try:
        async for data, _ in response.content.iter_chunks():
            for audit_log in _streamed_audit_log(data):
                audit_logs.append(audit_log)
                if audit_log['ref_table'] == 'blueprints' \
                        and audit_log['operation'] == 'delete':
                    response.close()
                    break
    except Exception as ex:
        assert type(ex) == asyncio.TimeoutError
    else:
        assert False


def _upload_blueprint(rest_client: CloudifyClient):
    blueprint_id = 'bp'
    blueprint = rest_client.blueprints.upload(
        resource('dsl/empty_blueprint.yaml'),
        entity_id=blueprint_id)
    assert blueprint.id == blueprint_id
    return blueprint


def _streamed_audit_log(data: bytes) -> Sequence[dict]:
    for line in data.split(b'\n\n'):
        if line:
            yield json.loads(line.decode())


def _filter_logs(logs: List[dict], **kwargs) -> List[dict]:
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

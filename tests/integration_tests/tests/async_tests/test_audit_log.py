import asyncio
import json
from typing import List

import aiohttp
import pytest

from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_api


@pytest.mark.asyncio
async def test_audit_log_stream(async_client, rest_client):
    response = await async_client.get('audit/stream',
                                      timeout=aiohttp.ClientTimeout(total=30))
    assert response.status == 200
    assert response.headers.get('Content-Type') == 'text/event-stream'

    blueprint_id = 'bp'
    blueprint = rest_client.blueprints.upload(
        resource('dsl/empty_blueprint.yaml'),
        entity_id=blueprint_id)
    rest_client.blueprints.delete(blueprint_id)

    audit_logs = []
    try:
        async for data, _ in response.content.iter_chunks():
            for line in data.split(b'\n\n'):
                if line:
                    audit_log = json.loads(line.decode())
                    audit_logs.append(audit_log)
                    if audit_log['ref_table'] == 'blueprints' \
                            and audit_log['operation'] == 'delete':
                        response.close()
                        break
    except (asyncio.TimeoutError, aiohttp.ClientConnectionError):
        pass

    assert len(filter_logs(audit_logs,
                           ref_table='blueprints',
                           operation='create')) == 1
    assert len(filter_logs(audit_logs,
                           ref_table='blueprints',
                           operation='delete')) == 1
    assert len(filter_logs(audit_logs,
                           execution_id=blueprint.upload_execution['id'])) >= 1


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

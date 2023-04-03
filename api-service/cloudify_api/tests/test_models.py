from datetime import datetime

import pytz
import pytest
from pydantic.error_wrappers import ValidationError

from cloudify_api import models

TIMESTAMP = '2023-03-28T15:24:52+02:00'

VALID_SELECT_PARAMS = {
    'creator_name': 'admin',
    'execution_id': '123-456-7890',
    'since': datetime.fromisoformat(TIMESTAMP),
}


def test_select_params_ok():
    params = models.SelectParams.parse_obj(VALID_SELECT_PARAMS)
    assert params.creator_name == 'admin'
    assert params.execution_id == '123-456-7890'
    since_utc = params.since.astimezone(pytz.UTC)
    assert (since_utc.year, since_utc.month, since_utc.day) == (2023, 3, 28)
    assert (since_utc.hour, since_utc.minute, since_utc.second) == (13, 24, 52)


def test_select_params_since_and_before():
    with pytest.raises(ValidationError):
        models.SelectParams.parse_obj({
            'since': datetime.fromisoformat(TIMESTAMP),
            'before': datetime.fromisoformat(TIMESTAMP)
        })


def test_select_params_as_filters():
    params = models.SelectParams.parse_obj(VALID_SELECT_PARAMS)
    filters = params.as_filters()
    assert len(filters) == 3
    assert all(ex.left.table.name == 'audit_log' for ex in filters)
    assert {(ex.left.name, ex.right.value) for ex in filters} == {
        ('created_at', datetime.fromisoformat(TIMESTAMP)),
        ('creator_name', 'admin'),
        ('execution_id', '123-456-7890')
    }

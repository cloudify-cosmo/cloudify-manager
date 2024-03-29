from unittest import mock

import pytest

from cloudify_rest_client.blueprints import Blueprint
from cloudify_rest_client.deployments import Deployment
from cloudify_rest_client.responses import ListResponse
from cloudify_system_workflows.deployment_environment import create


EMPTY_BLUEPRINT_PLAN = {
    'inputs': {},
    'nodes': {},
    'outputs': {},
    'scaling_groups': {},
    'description': None,
    'workflows': {},
    'policy_types': {},
    'policy_triggers': {},
    'groups': {}
}


@pytest.fixture(autouse=True)
def mock_create_workdir():
    with mock.patch(
        'cloudify_system_workflows.deployment_environment'
        '._create_deployment_workdir'
    ):
        yield


@pytest.fixture()
def mock_ctx():
    ctx = mock.Mock()
    ctx.blueprint.id = 'bp1'
    ctx.deployment.id = 'd1'
    yield ctx


@pytest.fixture
def blueprint_plan(mock_ctx):
    yield EMPTY_BLUEPRINT_PLAN.copy()


@pytest.fixture
def mock_client(blueprint_plan):
    client = mock.Mock()
    bp = Blueprint({'plan': blueprint_plan})
    dep = Deployment({})
    client.blueprints.get.return_value = bp
    client.deployments.set_attributes.return_value = dep

    client.node_instances.list = \
        lambda node_id, _offset, **kwargs: ListResponse(
            [], {'pagination': {'total': 0, 'size': 1000}})
    client.evaluate.functions = lambda dep, ctx, obj: {'payload': obj}
    with mock.patch(
        'cloudify_system_workflows.deployment_environment.get_rest_client',
        return_value=client
    ):
        yield client


def test_calls_set_attributes(mock_ctx, mock_client):
    """create() ends up calling set_attributes"""
    create(mock_ctx)
    attr_calls = mock_client.deployments.set_attributes.mock_calls
    assert len(attr_calls) == 1
    call = attr_calls[0]
    assert call.args[0] == mock_ctx.deployment.id


def test_sets_description(mock_ctx, mock_client, blueprint_plan):
    """create() passes the description from the plan to set_attributes

    description is not all that interesting by itself, but this test
    should serve as a good example for writing other tests
    """
    blueprint_plan['description'] = 'desc1'
    create(mock_ctx)
    call = mock_client.deployments.set_attributes.mock_calls[0]
    assert call.args[0] == mock_ctx.deployment.id
    assert call.kwargs['description'] == 'desc1'


def test_joins_groups(mock_ctx, mock_client, blueprint_plan):
    groups = ['g1', 'g2', 'g3']
    blueprint_plan['deployment_settings'] = {
        'default_groups': groups
    }
    create(mock_ctx)
    group_calls = mock_client.deployment_groups.add_deployments.mock_calls
    assert len(group_calls) == len(groups)
    for mock_join_call in group_calls:
        joined_group_id = mock_join_call.args[0]
        assert joined_group_id in groups
        groups.remove(joined_group_id)
        assert mock_join_call.kwargs['deployment_ids'] == \
            [mock_ctx.deployment.id]


def test_labels_from_plan(mock_ctx, mock_client, blueprint_plan):
    blueprint_plan['labels'] = {'a': {'values': ['b']}}
    create(mock_ctx)
    call = mock_client.deployments.set_attributes.mock_calls[0]
    assert call.kwargs['labels'] == [{'a': 'b'}]


def test_labels_from_kwargs(mock_ctx, mock_client):
    create(mock_ctx, labels=[{'key': 'a', 'value': 'b'}])
    call = mock_client.deployments.set_attributes.mock_calls[0]
    assert call.kwargs['labels'] == [{'a': 'b'}]


def test_labels_from_plan_and_kwargs(mock_ctx, mock_client, blueprint_plan):
    blueprint_plan['labels'] = {'a': {'values': ['c']}}
    create(mock_ctx, labels=[{'key': 'a', 'value': 'b'}])
    call = mock_client.deployments.set_attributes.mock_calls[0]
    assert len(call.kwargs['labels']) == 2
    assert {'a': 'b'} in call.kwargs['labels']
    assert {'a': 'c'} in call.kwargs['labels']


def test_inputs(mock_ctx, mock_client, blueprint_plan):
    def parse_inputs(obj):
        if 'input_constraints' in obj:
            # we're in the "evaluate input constraints" call
            constraints = obj['input_constraints']
            assert constraints['a'][0]['valid_values'] == \
                   ['x', {'get_secret': 's1'}]
            assert constraints['b'][0]['valid_values'] == \
                   [{'get_secret': 's1'}, {'get_secret': 's2'}]

            # Mock parse values
            constraints['a'][0]['valid_values'] = ['x', 'y']
            constraints['b'][0]['valid_values'] = ['y', 'z']
        return obj

    blueprint_plan['inputs'] = {
        'a': {
            'type': 'string',
            'constraints': [{
                'valid_values': [
                    'x',
                    {'get_secret': 's1'},
                ]
            }]
        },
        'b': {
            'type': 'string',
            'constraints': [{
                'valid_values': [
                    {'get_secret': 's1'},
                    {'get_secret': 's2'},
                ]
            }]
        },

    }

    mock_client.evaluate.functions = lambda dep, ctx, obj: {
        'payload': parse_inputs(obj)
    }
    create(mock_ctx, inputs={'a': 'x', 'b': 'z'})
    call = mock_client.deployments.set_attributes.mock_calls[0]
    assert len(call.kwargs['inputs']) == 2
    assert call.kwargs['inputs'].get('a') == 'x'
    assert call.kwargs['inputs'].get('b') == 'z'

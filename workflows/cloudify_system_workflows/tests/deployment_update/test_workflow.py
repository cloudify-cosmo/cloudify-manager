import os

import pytest

from cloudify.constants import NODE_INSTANCE, RELATIONSHIP_INSTANCE
from cloudify.exceptions import NonRecoverableError
from cloudify.workflows import local


def dsl_path_base():
    return os.path.join(os.path.dirname(__file__), 'blueprints')


def deploy(blueprint_filename, resource_id='d1', storage=None, inputs=None):
    if storage is None:
        storage = local.InMemoryStorage()
    blueprint_path = os.path.join(dsl_path_base(), blueprint_filename)
    storage.create_blueprint(resource_id, blueprint_path)
    storage.create_deployment(resource_id, resource_id, inputs=inputs)
    return storage


def test_empty_update():
    storage = deploy('empty.yaml', resource_id='d1')
    dep_env = local.load_env('d1', storage)
    storage.create_deployment_update('d1', 'update1', {})
    dep_env.execute('update', parameters={'update_id': 'update1'})
    executions = dep_env.storage.get_executions()
    assert len(executions) == 1
    assert executions[0]['workflow_id'] == 'update'
    assert executions[0]['status'] == 'terminated'


def test_run_update_workflow():
    storage = deploy('empty.yaml', resource_id='d1')
    storage.create_blueprint(
        'bp2',
        os.path.join(dsl_path_base(), 'description.yaml'),
    )
    original_description = storage.get_deployment('d1').description
    dep_env = local.load_env('d1', storage)
    storage.create_deployment_update('d1', 'update1', {
        'new_blueprint_id': 'bp2',
    })
    dep_env.execute('update', parameters={'update_id': 'update1'})
    changed_description = storage.get_deployment('d1').description
    assert changed_description != original_description


def test_change_property():
    storage = deploy('property_input.yaml', resource_id='d1', inputs={
        'inp1': 'value1',
    })
    dep_env = local.load_env('d1', storage)
    dep_env.execute('install')
    storage.create_deployment_update('d1', 'update1', {
        'new_inputs': {'inp1': 'value2'}
    })
    dep_env.execute('update', parameters={'update_id': 'update1'})
    # reload the storage to get the updated deployment + node
    dep_env = local.load_env('d1', storage)
    node = dep_env.storage.get_node('n1', evaluate_functions=True)
    assert node.properties['prop1'] == 'value2'


@pytest.mark.parametrize('blueprint_filename,parameters,install', [
    ('update_operation.yaml', {}, True),
    ('skip_drift_check.yaml', {
        'skip_drift_check': True,
    }, True),
    ('force_reinstall.yaml', {
        'force_reinstall': True,
    }, True),
    ('without_install.yaml', {}, False),
])
def test_update_operation(subtests, blueprint_filename, parameters, install):
    """Test the update instances flow.

    This function is essentially just the driver code, and the actual cases
    and expectations are encoded in the blueprint itself.
    """
    storage = deploy(blueprint_filename, resource_id='d1', inputs={
        'inp1': 'value1',
    })
    dep_env = local.load_env('d1', storage)

    if install:
        dep_env.execute('install')
    else:
        # local deployments don't currently default status to uninitialized,
        # but they leave it as none. Let's default it, so that the uninstall
        # graph doesn't do anything
        for ni in dep_env.storage.get_node_instances():
            dep_env.storage.update_node_instance(
                ni.id, state='uninitialized',
                force=True,
                version=0,
            )

    storage.create_deployment_update('d1', 'update1', {
        'new_inputs': {'inp1': 'value2'}
    })
    parameters['update_id'] = 'update1'
    dep_env.execute('update', parameters=parameters)

    for ni in dep_env.storage.get_node_instances():
        with subtests.test(ni.node_id):
            node = dep_env.storage.get_node(ni.node_id)
            actual_calls = ni.runtime_properties.get('invocations', [])
            expected_calls = node.properties.get('expected_calls') or []
            assert actual_calls == expected_calls


def test_reinstall_list():
    storage = deploy('force_reinstall.yaml', resource_id='d1', inputs={
        'inp1': 'value1',
    })
    dep_env = local.load_env('d1', storage)
    dep_env.execute('install')

    instances = dep_env.storage.get_node_instances()
    assert len(instances) == 1
    ni_id = instances[0].id

    storage.create_deployment_update('d1', 'update1', {
        'new_inputs': {'inp1': 'value1'},  # unchanged
    })

    # updating with reinstall_list, reinstalls that instance, even though
    # nothing has changed
    dep_env.execute('update', parameters={
        'update_id': 'update1',
        'reinstall_list': [ni_id]
    })
    inst = dep_env.storage.get_node_instance(ni_id)
    assert inst.runtime_properties['invocations'] == ['create']

    # reinstall_list overrides even skip_reinstall!
    dep_env.execute('update', parameters={
        'update_id': 'update1',
        'reinstall_list': [ni_id],
        'skip_reinstall': True,
    })
    inst = dep_env.storage.get_node_instance(ni_id)
    assert inst.runtime_properties['invocations'] == ['create', 'create']


def test_establish_operation():
    """Check relationship setup during update

    Update doesn't run establish operations for instances that aren't
    installed (e.g. because they were just added, and not installed yet).
    Establish operations are only run for instances that are installed.
    """
    storage = deploy('single_relationship.yaml', resource_id='d1')
    dep_env = local.load_env('d1', storage)

    # install only node n1, but not n2
    dep_env.execute('install', parameters={'node_ids': ['n1']})

    n1_instances = dep_env.storage.get_node_instances(node_id='n1')
    n2_instances = dep_env.storage.get_node_instances(node_id='n2')
    assert len(n1_instances) == 1
    assert len(n2_instances) == 1
    n1_instance = n1_instances[0]
    n2_instance = n2_instances[0]
    assert n1_instance.state == 'started'
    assert n2_instance.state in ('uninitialized', None)

    # now run an empty update, and check that we did NOT see any establish
    # operations run - the relationship is declared, but n2 is not installed
    storage.create_deployment_update('d1', 'update1', {
        # no parameters, just drift-only update
    })
    dep_env.execute('update', parameters={'update_id': 'update1'})

    n1_instance = dep_env.storage.get_node_instance(n1_instance.id)
    n2_instance = dep_env.storage.get_node_instance(n2_instance.id)
    assert n1_instance.runtime_properties['invocations'] == \
        ['check_drift', 'create']
    assert not n2_instance.runtime_properties.get('invocations')

    # now install n2!
    dep_env.execute('install', parameters={'node_ids': ['n2']})
    n2_instance = dep_env.storage.get_node_instance(n2_instance.id)
    assert n2_instance.state == 'started'

    # now run another update. This one will run establish, because
    # n1 had to be reinstalled.
    storage.create_deployment_update('d1', 'update2', {
        # no parameters, just drift-only update
    })
    dep_env.execute('update', parameters={'update_id': 'update2'})

    n1_instance = dep_env.storage.get_node_instance(n1_instance.id)
    n2_instance = dep_env.storage.get_node_instance(n2_instance.id)
    assert n1_instance.runtime_properties['invocations'] == [
        'check_drift', 'create',  # from the previous update
        'check_drift', 'create', 'target_establish',  # from this update
    ]
    assert n2_instance.runtime_properties['invocations'] == [
        'source_establish'
    ]


def op(ctx, return_value=None, fail=False):
    """Operation used in the update-operation test.

    Store the call in runtime-properties, and return the given value, or fail.
    """
    if ctx.workflow_id != 'update':
        return
    if ctx.type == RELATIONSHIP_INSTANCE:
        if ctx._context['related']['is_target']:
            prefix = 'target_'
            instance = ctx.target.instance
        else:
            prefix = 'source_'
            instance = ctx.source.instance
    elif ctx.type == NODE_INSTANCE:
        instance = ctx.instance
        prefix = ''
    else:
        raise NonRecoverableError(f'unknown ctx.type: {ctx.type}')

    if 'invocations' not in instance.runtime_properties:
        instance.runtime_properties['invocations'] = []
    name = prefix + ctx.operation.name.split('.')[-1]
    invocations = instance.runtime_properties['invocations']
    invocations.append(name)
    instance.runtime_properties['invocations'] = invocations
    if fail:
        raise NonRecoverableError()
    return return_value

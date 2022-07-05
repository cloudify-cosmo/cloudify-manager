import os

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
    storage.create_deployment_update('d1', 'update1', {
        'new_inputs': {'inp1': 'value2'}
    })
    dep_env.execute('update', parameters={'update_id': 'update1'})
    # reload the storage to get the updated deployment + node
    dep_env = local.load_env('d1', storage)
    node = dep_env.storage.get_node('n1', evaluate_functions=True)
    assert node.properties['prop1'] == 'value2'

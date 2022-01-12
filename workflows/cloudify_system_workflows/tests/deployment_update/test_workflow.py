import os

from cloudify.workflows import local


def dsl_path_base():
    return os.path.join(os.path.dirname(__file__), 'blueprints')


def test_run_update_workflow():
    storage = local.InMemoryStorage()
    storage.create_blueprint(
        'bp1',
        os.path.join(dsl_path_base(), 'empty.yaml'),
    )
    storage.create_blueprint(
        'bp2',
        os.path.join(dsl_path_base(), 'description.yaml'),
    )
    storage.create_deployment('dep1', 'bp1')
    original_description = storage.get_deployment('dep1').description
    dep_env = local.load_env('dep1', storage)
    storage.create_deployment_update('dep1', 'update1', {
        'id': 'update1',
        'new_blueprint_id': 'bp2',
        'new_inputs': {},
        'runtime_only_evaluation': False,
        'deployment_id': 'dep1',
    })
    dep_env.execute('update', parameters={'update_id': 'update1'})
    changed_description = storage.get_deployment('dep1').description
    assert changed_description != original_description

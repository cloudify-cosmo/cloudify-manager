import pytest

from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_scale


@pytest.mark.usefixtures('cloudmock_plugin')
class TestScaleResume(AgentlessTestCase):
    def test_scale_resume(self):
        bp = self.make_yaml_file("""
tosca_definitions_version: cloudify_dsl_1_4

imports:
    - cloudify/types/types.yaml
    - plugin:cloudmock
node_types:
    t1:
        derived_from: cloudify.nodes.Root
        properties:
            allowed:
                type: integer
node_templates:
    n1:
        type: t1
        properties:
            allowed: {get_secret: allowed_instances}
        interfaces:
            cloudify.interfaces.lifecycle:
                create: cloudmock.cloudmock.tasks.limit_scale

        instances:
          deploy: 1
    n2:
        type: cloudify.nodes.Root
        relationships:
            - target: n1
              type: cloudify.relationships.contained_in
""")
        self.client.secrets.create('allowed_instances', '2')
        dep, _ = self.deploy_application(bp)
        # start a scale: this will fail, because the allowed_instances secret
        # is set to 2, so we only allow 2 instances to exist.
        # With rollback_if_failed=False, the modification will be left around
        # in the 'started'/unfinished state - failing node instances will be
        # created, but they will not be started.
        exc = self.execute_workflow('scale', dep.id, parameters={
            'scalable_entity_name': 'n1',
            'delta': 3,
            'rollback_if_failed': False,
        }, wait_for_execution=False)
        with self.assertRaises(RuntimeError):
            self.wait_for_execution_to_end(exc)

        node_instances = self.client.node_instances.list(deployment_id=dep.id)
        # new node instances were created
        assert len(node_instances) == 8
        # ...but they weren't all started
        assert not all(ni['state'] == 'started' for ni in node_instances)

        # update the secret to allow more instances to be started. Now, the
        # scale can be resumed, and the new instances will be able to start
        self.client.secrets.update('allowed_instances', '4')
        self.client.executions.resume(exc.id)
        self.wait_for_execution_to_end(exc)

        node_instances = self.client.node_instances.list(deployment_id=dep.id)
        assert len(node_instances) == 8
        assert all(ni['state'] == 'started' for ni in node_instances)

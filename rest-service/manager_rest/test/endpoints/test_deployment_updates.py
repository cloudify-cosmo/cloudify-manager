from manager_rest.test import base_test
from manager_rest.storage import models

from cloudify_rest_client.exceptions import CloudifyClientError
from manager_rest.execution_token import set_current_execution


class TestDeploymentUpdates(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        self.bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        self.dep = self._deployment(id='dep1')
        self.execution = models.Execution(
            id='exc1', deployment=self.dep, workflow_id='update')
        set_current_execution(self.execution)
        self.addCleanup(set_current_execution, None)

    def _deployment(self, **kwargs):
        params = {
            'blueprint': self.bp,
            'creator': self.user,
            'tenant': self.tenant,
            'inputs': {},
        }
        params.update(kwargs)
        return models.Deployment(**params)

    def test_create_dep_update(self):
        dep_up = self.client.deployment_updates.create('update1', self.dep.id)
        assert dep_up.deployment_id == self.dep.id
        # and using the more-frills method
        dep_up = self.client.deployment_updates.update_with_existing_blueprint(
            self.dep.id, inputs={'new': 'input'})
        assert dep_up.deployment_id == self.dep.id

    def test_set_update_attributes(self):
        new_plan = {'plan': 'xxx'}
        new_nodes = [{'name': 'node1'}]
        new_node_instances = [{'id': 'node1_abcdef'}]

        dep_up = self.client.deployment_updates.create('update1', self.dep.id)
        self.client.deployment_updates.set_attributes(
            'update1',
            plan=new_plan,
            nodes=new_nodes,
            node_instances=new_node_instances,
            state='successful',
        )
        dep_up = self.sm.get(models.DeploymentUpdate, 'update1')
        assert dep_up.deployment_plan == new_plan
        assert dep_up.deployment_update_nodes == new_nodes
        assert dep_up.deployment_update_node_instances == new_node_instances
        assert dep_up.state == 'successful'
        assert self.dep.updated_at is not None

    def test_set_update_steps(self):
        steps_to_create = [
            {
                'action': 'add',
                'entity_id': 'a',
                'entity_type': 'node',
                'topology_order': 0,
            },
            {
                'action': 'remove',
                'entity_id': 'b',
                'entity_type': 'relationship',
                'topology_order': 1,
            }
        ]
        self.client.deployment_updates.create('update1', self.dep.id)
        self.client.deployment_updates.set_attributes(
            'update1',
            steps=steps_to_create
        )
        steps = self.sm.list(
            models.DeploymentUpdateStep, sort={'topology_order': 'asc'})

        assert len(steps) == len(steps_to_create)
        for step_spec, actual_step in zip(steps_to_create, steps):
            assert step_spec['action'] == actual_step.action
            assert step_spec['entity_id'] == actual_step.entity_id
            assert step_spec['entity_type'] == actual_step.entity_type
            assert step_spec['topology_order'] == actual_step.topology_order
            assert actual_step.deployment_update.id == 'update1'

    def test_set_runtime_eval(self):
        for dep_runtime_eval in [True, False]:
            self.dep.runtime_only_evaluation = dep_runtime_eval
            dep_up = self.client.deployment_updates.\
                update_with_existing_blueprint(
                    self.dep.id,
                    inputs={'new': 'input'},
                    runtime_only_evaluation=None
                )
            assert dep_up.runtime_only_evaluation == dep_runtime_eval

    def test_invalid_parameters(self):
        for parameters in [
            {'inputs': {'a': 'b'}, 'reinstall_list': 'not_a_list'},
            {'inputs': 'not a dict'},
            {},  # missing inputs and blueprint-id
            {'inputs': {'a': 'b'}, 'preview': ['not a bool']}
        ]:
            with self.assertRaises(CloudifyClientError):
                self.client.deployment_updates.\
                    update_with_existing_blueprint(
                        self.dep.id,
                        **parameters
                    )

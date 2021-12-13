from manager_rest.storage import models, db

from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.models_states import DeploymentState

from manager_rest.test.base_test import BaseServerTestCase


class DeploymentLabelsDependenciesTest(BaseServerTestCase):

    def setUp(self):
        super().setUp()
        self.blueprint = models.Blueprint(
            tenant=self.tenant,
            creator=self.user,
        )

    def _deployment(self, **kwargs):
        dep_attrs = {
            'blueprint': self.blueprint,
            'tenant': self.tenant,
            'creator': self.user
        }
        dep_attrs.update(kwargs)
        dep = models.Deployment(**dep_attrs)
        db.session.add(dep)
        return dep

    def test_deployment_with_single_parent_label(self):
        parent = self._deployment(id='parent')
        self._deployment(id='dep')

        self.client.deployments.set_attributes(
            'dep',
            labels=[{'csys-obj-parent': 'parent'}]
        )
        assert parent.sub_services_count == 1
        assert parent.sub_environments_count == 0

    def test_deploy_blueprint_with_invalid_parent_id(self):
        self._deployment(id='dep')
        with self.assertRaisesRegex(CloudifyClientError, 'not found'):
            self.client.deployments.set_attributes(
                'dep',
                labels=[{'csys-obj-parent': 'parent'}]
            )

    def test_deployment_with_multiple_parent_labels(self):
        parent1 = self._deployment(id='parent1')
        parent2 = self._deployment(id='parent2')
        self._deployment(id='dep')

        self.client.deployments.set_attributes(
            'dep',
            labels=[
                {'csys-obj-parent': 'parent1'},
                {'csys-obj-parent': 'parent2'}
            ]
        )
        assert parent1.sub_services_count == 1
        assert parent1.sub_environments_count == 0
        assert parent2.sub_services_count == 1
        assert parent2.sub_environments_count == 0

    def test_deployment_with_valid_and_invalid_parent_labels(self):
        parent = self._deployment(id='parent')
        self._deployment(id='dep')
        with self.assertRaisesRegex(CloudifyClientError, 'not found'):
            self.client.deployments.set_attributes(
                'dep',
                labels=[
                    {'csys-obj-parent': 'parent'},
                    {'csys-obj-parent': 'nonexistent'}
                ]
            )
        assert parent.sub_services_count == 0
        assert parent.sub_environments_count == 0

    def test_add_valid_label_parent_to_created_deployment(self):
        parent1 = self._deployment(id='parent1')
        parent2 = self._deployment(id='parent2')
        self._deployment(id='dep')

        self.client.deployments.set_attributes(
            'dep',
            labels=[{'csys-obj-parent': 'parent1'}]
        )
        assert parent1.sub_services_count == 1
        assert parent1.sub_environments_count == 0

        self.client.deployments.update_labels('dep', [
            {'csys-obj-parent': 'parent1'},
            {'csys-obj-parent': 'parent2'}
        ])
        assert parent1.sub_services_count == 1
        assert parent1.sub_environments_count == 0
        assert parent2.sub_services_count == 1
        assert parent2.sub_environments_count == 0

    def test_add_invalid_label_parent_to_created_deployment(self):
        self._deployment(id='dep')
        with self.assertRaisesRegex(CloudifyClientError, 'not found'):
            self.client.deployments.update_labels('dep', [
                {'csys-obj-parent': 'notexist'}
            ])

    def test_cyclic_dependencies_between_deployments(self):
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        self.client.deployments.set_attributes(
            'dep2',
            labels=[{'csys-obj-parent': 'dep1'}]
        )
        with self.assertRaisesRegex(CloudifyClientError, 'cyclic'):
            self.client.deployments.update_labels('dep1', [
                {'csys-obj-parent': 'dep2'}
            ])
        assert dep1.sub_services_count == 1
        assert dep2.sub_services_count == 0
        assert len(dep1.labels) == 0

    def test_number_of_direct_services_deployed_inside_environment(self):
        self._deployment(id='env')
        self._deployment(id='dep1')
        self._deployment(id='dep2')
        for dep_name in ['dep1', 'dep2']:
            self.client.deployments.set_attributes(
                dep_name,
                labels=[{'csys-obj-parent': 'env'}]
            )
        deployment = self.client.deployments.get(
            'env', all_sub_deployments=False)
        assert deployment.sub_services_count == 2

    def test_number_of_total_services_deployed_inside_environment(self):
        env1 = self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='dep1')
        self._deployment(id='dep2')
        self._deployment(id='dep3')
        self._deployment(id='dep4')
        self.client.deployments.update_labels(
            'env1',
            labels=[{'csys-obj-type': 'environment'}]
        )
        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        for dep_name in ['dep1', 'dep2']:
            self.client.deployments.update_labels(
                dep_name,
                labels=[{'csys-obj-parent': 'env1'}]
            )
        for dep_name in ['dep3', 'dep4']:
            self.client.deployments.update_labels(
                dep_name,
                labels=[{'csys-obj-parent': 'env2'}]
            )

        assert env1.sub_services_count == 4
        deployment = self.client.deployments.get('env1')
        assert deployment.sub_services_count == 4
        deployment = self.client.deployments.get('env1',
                                                 all_sub_deployments=False)
        assert deployment.sub_services_count == 2

    def test_number_of_direct_environments_deployed_inside_environment(self):
        self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='env3')
        self.client.deployments.update_labels(
            'env1',
            labels=[{'csys-obj-type': 'environment'}]
        )
        for env_name in ['env2', 'env3']:
            self.client.deployments.update_labels(
                env_name,
                labels=[
                    {'csys-obj-type': 'environment'},
                    {'csys-obj-parent': 'env1'}
                ]
            )
        deployment = self.client.deployments.get(
            'env1', all_sub_deployments=False)
        assert deployment.sub_environments_count == 2

    def test_number_of_total_environments_deployed_inside_environment(self):
        self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='env3')
        self._deployment(id='env4')
        self.client.deployments.update_labels(
            'env1',
            labels=[{'csys-obj-type': 'environment'}]
        )
        for env_name in ['env2', 'env3']:
            self.client.deployments.update_labels(
                env_name,
                labels=[
                    {'csys-obj-type': 'environment'},
                    {'csys-obj-parent': 'env1'}
                ]
            )
        self.client.deployments.update_labels(
            'env4',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env2'}
            ]
        )
        deployment = self.client.deployments.get('env1')
        self.assertEqual(deployment.sub_environments_count, 3)
        deployment = self.client.deployments.get('env1',
                                                 all_sub_deployments=False)
        self.assertEqual(deployment.sub_environments_count, 2)

    def test_detach_all_services_from_deployment(self):
        env1 = self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        self.client.deployments.update_labels(
            'srv1',
            labels=[
                {'csys-obj-parent': 'env1'}
            ]
        )
        assert env1.sub_services_count == 1
        assert env1.sub_environments_count == 1

        self.client.deployments.update_labels(
            'srv1',
            labels=[{'csys-obj-type': 'service'}]
        )
        assert env1.sub_services_count == 0
        assert env1.sub_environments_count == 1

    def test_detach_all_environments_from_deployment(self):
        env1 = self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        self.client.deployments.update_labels(
            'srv1',
            labels=[
                {'csys-obj-parent': 'env1'}
            ]
        )
        assert env1.sub_services_count == 1
        assert env1.sub_environments_count == 1

        self.client.deployments.update_labels(
            'env2',
            labels=[{'csys-obj-type': 'service'}]
        )
        assert env1.sub_services_count == 1
        assert env1.sub_environments_count == 0

    def test_deployment_statuses_after_creation_without_sub_deployments(self):
        bp = models.Blueprint(id='bp1', creator=self.user, tenant=self.tenant,
                              plan={}, state='uploaded')
        db.session.add(bp)
        self.client.deployments.create('bp1', 'dep1')
        dep1 = db.session.query(models.Deployment).filter_by(id='dep1').one()

        assert dep1.deployment_status == DeploymentState.REQUIRE_ATTENTION
        assert dep1.sub_services_status is None
        assert dep1.sub_environments_status is None

        exc = models.Execution(
            id='exc1',
            _deployment_fk=dep1._storage_id,
            workflow_id='create_deployment_environment',
            tenant=self.tenant,
            creator=self.user,
        )
        db.session.add(exc)
        self.client.executions.update(exc.id, status='terminated')
        assert dep1.deployment_status == DeploymentState.GOOD

    def test_deployment_statuses_after_creation_with_sub_deployments(self):
        env1 = self._deployment(id='env1')
        env2 = self._deployment(id='env2')
        srv1 = self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        self.client.deployments.update_labels(
            'srv1',
            labels=[{'csys-obj-parent': 'env1'}]
        )
        for dep in [env1, env2, srv1]:
            exc = models.Execution(
                id=f'create_{dep.id}',
                _deployment_fk=dep._storage_id,
                workflow_id='create_deployment_environment',
                tenant=self.tenant,
                creator=self.user,
            )
            db.session.add(exc)
            self.client.executions.update(exc.id, status='terminated')
        assert env1.deployment_status == DeploymentState.GOOD
        assert env1.sub_services_status == DeploymentState.GOOD
        assert env1.sub_environments_status == DeploymentState.GOOD

    def test_delete_deployment_with_sub_deployments(self):
        self._deployment(id='env1')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'srv1',
            labels=[{'csys-obj-parent': 'env1'}]
        )
        with self.assertRaises(CloudifyClientError):
            self.client.deployments.delete('env1')

    def test_stop_deployment_with_sub_deployments(self):
        self._deployment(id='env1')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'srv1',
            labels=[{'csys-obj-parent': 'env1'}]
        )
        with self.assertRaises(CloudifyClientError):
            self.client.executions.start('parent', 'stop')

    def test_uninstall_deployment_with_sub_deployments(self):
        self._deployment(id='env1')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'srv1',
            labels=[{'csys-obj-parent': 'env1'}]
        )
        with self.assertRaises(CloudifyClientError):
            self.client.executions.start('parent', 'uninstall')

    def test_sub_deployments_counts_after_convert_to_service(self):
        env1 = self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        self.client.deployments.update_labels(
            'srv1',
            labels=[
                {'csys-obj-parent': 'env1'}
            ]
        )
        assert env1.sub_services_count == 1
        assert env1.sub_environments_count == 1

        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'service'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        assert env1.sub_services_count == 2
        assert env1.sub_environments_count == 0

    def test_sub_deployments_counts_after_convert_to_environment(self):
        env1 = self._deployment(id='env1')
        self._deployment(id='env2')
        self._deployment(id='srv1')
        self.client.deployments.update_labels(
            'env2',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        self.client.deployments.update_labels(
            'srv1',
            labels=[
                {'csys-obj-parent': 'env1'}
            ]
        )
        assert env1.sub_services_count == 1
        assert env1.sub_environments_count == 1

        self.client.deployments.update_labels(
            'srv1',
            labels=[
                {'csys-obj-type': 'environment'},
                {'csys-obj-parent': 'env1'}
            ]
        )
        assert env1.sub_services_count == 0
        assert env1.sub_environments_count == 2

    def test_csys_env_type(self):
        dep1 = self._deployment(id='dep1')
        assert dep1.environment_type == ''
        self.client.deployments.update_labels(
            'dep1',
            labels=[
                {'csys-env-type': 'subcloud'}
            ]
        )
        assert dep1.environment_type == 'subcloud'

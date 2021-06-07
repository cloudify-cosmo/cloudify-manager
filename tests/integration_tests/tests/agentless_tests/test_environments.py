import time

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

from cloudify.models_states import DeploymentState

from cloudify_rest_client.exceptions import CloudifyClientError

pytestmark = pytest.mark.group_environments


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('mock_workflows_plugin')
@pytest.mark.usefixtures('testmockoperations_plugin')
class EnvironmentTest(AgentlessTestCase):

    def _deploy_main_environment(self, resource_path,
                                 blueprint_id=None,
                                 deployment_id=None):
        dsl_path = resource(resource_path)
        deployment, _ = self.deploy_application(dsl_path,
                                                blueprint_id=blueprint_id,
                                                deployment_id=deployment_id)

        self.client.deployments.update_labels(
            deployment.id,
            [
                {
                    'csys-obj-type': 'Environment'
                },

            ]
        )
        return deployment

    def _assert_main_environment_after_installation(self, environment_id,
                                                    deployment_status):
        environment = self.client.deployments.get(environment_id)
        # The environment itself is deployed and installed correctly
        self.assertEqual(
            environment.deployment_status,
            deployment_status
        )

    def _assert_deployment_environment_attr(self,
                                            deployment,
                                            deployment_status,
                                            sub_services_status=None,
                                            sub_environments_status=None,
                                            sub_services_count=0,
                                            sub_environments_count=0):
        self.assertEqual(
            deployment.deployment_status,
            deployment_status
        )
        self.assertEqual(
            deployment.sub_services_status,
            sub_services_status
        )
        self.assertEqual(
            deployment.sub_environments_status,
            sub_environments_status
        )
        self.assertEqual(
            deployment.sub_services_count,
            sub_services_count
        )
        self.assertEqual(
            deployment.sub_environments_count,
            sub_environments_count
        )

    def _verify_statuses_and_count_for_deployment(self,
                                                  deployment_id,
                                                  deployment_status,
                                                  sub_services_status=None,
                                                  sub_environments_status=None,
                                                  sub_services_count=0,
                                                  sub_environments_count=0):
        deployment = self.client.deployments.get(deployment_id)
        self._assert_deployment_environment_attr(
            deployment,
            deployment_status,
            sub_services_status,
            sub_environments_status,
            sub_services_count,
            sub_environments_count
        )

    def _attach_deployment_to_parents(self, deployment_id, parents_ids,
                                      deployment_type):
        if not parents_ids:
            return
        parents = []
        for parent_id in parents_ids:
            parents.append({'csys-obj-parent': parent_id})
        labels = [{'csys-obj-type': deployment_type}]
        labels.extend(parents)
        self.client.deployments.update_labels(deployment_id, labels)

    def _deploy_deployment_to_environment(self,
                                          environment,
                                          resource_path,
                                          deployment_type,
                                          blueprint_id=None,
                                          deployment_id=None,
                                          install=False):
        dsl_path = resource(resource_path)
        if not install:
            deployment = self.deploy(dsl_path,
                                     blueprint_id=blueprint_id,
                                     deployment_id=deployment_id)
        else:
            deployment, _ = self.deploy_application(dsl_path)
        self._attach_deployment_to_parents(
            deployment.id,
            [environment.id],
            deployment_type
        )
        return deployment

    def _deploy_environment_with_two_levels(self, main_environment):
        # # First environment
        env1 = self._deploy_deployment_to_environment(
            main_environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        # # Second environment
        env2 = self._deploy_deployment_to_environment(
            main_environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        # # Add service + environment to the env1
        service1, environment1 = \
            self._deploy_environment_with_service_and_environment(env1)

        # # Add service + environment to the env2
        service2, environment2 = \
            self._deploy_environment_with_service_and_environment(env2)
        return service1, environment1, service2, environment2

    def _deploy_environment_with_three_levels(self, main_environment):
        _, environment11, _, environment21 = \
            self._deploy_environment_with_two_levels(main_environment)

        service111, environment111 = \
            self._deploy_environment_with_service_and_environment(
                environment11
            )
        service211, environment211 = \
            self._deploy_environment_with_service_and_environment(
                environment21
            )
        return service111, environment111, service211, environment211

    def _deploy_environment_with_service_and_environment(self,
                                                         main_environment):
        service = self._deploy_deployment_to_environment(
            main_environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )

        environment = self._deploy_deployment_to_environment(
            main_environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        main_environment = self.client.deployments.get(main_environment.id)
        self._assert_deployment_environment_attr(
            main_environment,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_services_count=1,
            sub_environments_count=1
        )
        return service, environment

    def _create_deployment_group_from_blueprint(self,
                                                resource_path,
                                                blueprint_id,
                                                group_id,
                                                group_size,
                                                labels_to_add=None,
                                                wait_on_labels_add=12):
        # Upload group base blueprint
        self.upload_blueprint_resource(
            resource_path,
            blueprint_id
        )
        # Handle group actions
        self.client.deployment_groups.put(
            group_id, blueprint_id=blueprint_id
        )
        self.client.deployment_groups.add_deployments(
            group_id,
            count=group_size
        )
        # Wait till the deployment created successfully before adding any
        # labels in order to avoid any race condition
        if labels_to_add:
            time.sleep(wait_on_labels_add)
            self.client.deployment_groups.put(
                group_id,
                labels=labels_to_add,
            )

    def _execute_workflow_on_group(self, group_id, workflow_id):
        execution_group = self.client.execution_groups.start(
            deployment_group_id=group_id,
            workflow_id=workflow_id
        )
        self.wait_for_execution_to_end(execution_group, is_group=True)

    def test_create_deployment_with_invalid_parent_label(self):
        dsl_path = resource('dsl/basic.yaml')
        deployment = self.deploy(dsl_path)
        with self.assertRaises(CloudifyClientError):
            self._attach_deployment_to_parents(
                deployment.id,
                ['invalid_parent'],
                'service'
            )

    def test_environment_with_cyclic_dependencies(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service'
        )
        with self.assertRaises(CloudifyClientError):
            self._attach_deployment_to_parents(
                environment.id,
                [deployment.id],
                'environment'
            )

    def test_environment_after_deploy_single_service(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service'
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_count=1
        )

    def test_environment_after_deploy_multiple_services(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service'
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/empty_blueprint.yaml',
            'service'
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_count=2
        )

    def test_environment_after_install_single_service(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1
        )

    def test_environment_after_install_multiple_services(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/empty_blueprint.yaml',
            'service',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=2
        )

    def test_environment_after_install_single_service_with_failure(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/workflow_api.yaml',
            'service',
            install=True
        )
        with self.assertRaises(RuntimeError):
            self.execute_workflow(
                workflow_name='execute_operation',
                deployment_id=deployment.id,
                parameters={
                    'operation': 'test.fail',
                    'node_ids': ['test_node'],
                    'operation_kwargs': {'non_recoverable': True}
                },
                wait_for_execution=True
            )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_count=1
        )

    def test_environment_after_install_multiple_services_with_failure(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )
        service2 = self._deploy_deployment_to_environment(
            environment,
            'dsl/workflow_api.yaml',
            'service',
            install=True
        )

        with self.assertRaises(RuntimeError):
            self.execute_workflow(
                workflow_name='execute_operation',
                deployment_id=service2.id,
                parameters={
                    'operation': 'test.fail',
                    'node_ids': ['test_node'],
                    'operation_kwargs': {'non_recoverable': True}
                },
                wait_for_execution=True
            )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_count=2
        )

    def test_environment_after_deploy_single_environment(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment'
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_count=1
        )

    def test_environment_after_deploy_multiple_environments(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment'
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/empty_blueprint.yaml',
            'environment'
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_count=2
        )

    def test_environment_after_install_single_environment(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=1
        )

    def test_environment_after_install_multiple_environments(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/empty_blueprint.yaml',
            'environment',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=2
        )

    def test_environment_after_install_single_environment_with_failure(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/workflow_api.yaml',
            'environment',
            install=True
        )
        with self.assertRaises(RuntimeError):
            self.execute_workflow(
                workflow_name='execute_operation',
                deployment_id=deployment.id,
                parameters={
                    'operation': 'test.fail',
                    'node_ids': ['test_node'],
                    'operation_kwargs': {'non_recoverable': True}
                },
                wait_for_execution=True
            )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_count=1
        )

    def test_environment_after_install_multiple_environments_with_failure(
            self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/workflow_api.yaml',
            'environment',
            install=True
        )
        with self.assertRaises(RuntimeError):
            self.execute_workflow(
                workflow_name='execute_operation',
                deployment_id=deployment.id,
                parameters={
                    'operation': 'test.fail',
                    'node_ids': ['test_node'],
                    'operation_kwargs': {'non_recoverable': True}
                },
                wait_for_execution=True
            )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_count=2
        )

    def test_environment_after_install_service_and_environment(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )

        self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1,
            sub_environments_count=1
        )

    def test_environment_after_removing_service(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service'
        )
        environment = self.client.deployments.get(environment.id)
        self._assert_deployment_environment_attr(
            environment,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_count=1
        )
        self.delete_deployment(deployment.id, validate=True)
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_count=0
        )

    def test_environment_after_uninstall_service(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )
        environment = self.client.deployments.get(environment.id)
        self._assert_deployment_environment_attr(
            environment,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1
        )
        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=deployment.id,
                              wait_for_execution=True)
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_count=1
        )

    def test_environment_after_removing_environment(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment'
        )
        environment = self.client.deployments.get(environment.id)
        self._assert_deployment_environment_attr(
            environment,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_count=1
        )
        self.delete_deployment(deployment.id, validate=True)
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_count=0
        )

    def test_environment_after_uninstall_environment(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=1
        )
        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=deployment.id,
                              wait_for_execution=True)
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_count=1
        )

    def test_environment_after_update_workflow(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            main_environment,
            'dsl/simple_deployment.yaml',
            'service',
            install=True
        )
        main_environment = self.client.deployments.get(main_environment.id)
        self._assert_deployment_environment_attr(
            main_environment,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1
        )
        # Deploy new parent 1
        environment_1 = self._deploy_main_environment(
            'dsl/basic.yaml',
            blueprint_id='new_parent_1',
            deployment_id='new_parent_1'
        )
        # Deploy new parent 2
        environment_2 = self._deploy_main_environment(
            'dsl/basic.yaml',
            blueprint_id='new_parent_2',
            deployment_id='new_parent_2'
        )
        self._assert_main_environment_after_installation(
            environment_1.id, DeploymentState.GOOD
        )
        self._assert_main_environment_after_installation(
            environment_2.id, DeploymentState.GOOD
        )

        self.upload_blueprint_resource(
            'dsl/simple_deployment_with_parents.yaml',
            'updated-blueprint'
        )
        dep_up = self.client.deployment_updates.update_with_existing_blueprint(
            deployment.id,
            blueprint_id='updated-blueprint'
        )
        self.wait_for_execution_to_end(
            self.client.executions.get(dep_up.execution_id))
        self._verify_statuses_and_count_for_deployment(
            environment_1.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1
        )
        self._verify_statuses_and_count_for_deployment(
            environment_2.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1
        )

    def test_uninstall_environment_linked_with_multiple_deployments(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_environment_with_service_and_environment(environment)
        with self.assertRaises(CloudifyClientError):
            self.execute_workflow(workflow_name='uninstall',
                                  deployment_id=environment.id)

    def test_stop_environment_linked_with_multiple_deployments(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_environment_with_service_and_environment(environment)
        with self.assertRaises(CloudifyClientError):
            self.execute_workflow(workflow_name='stop',
                                  deployment_id=environment.id)

    def test_delete_environment_linked_with_multiple_deployments(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_environment_with_service_and_environment(environment)
        with self.assertRaises(CloudifyClientError):
            self.client.deployments.delete(environment.id)

    def test_update_environment_linked_with_multiple_deployments(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        self._deploy_environment_with_service_and_environment(environment)
        self.upload_blueprint_resource(
            'dsl/basic_get_secret.yaml',
            'updated_basic'
        )
        with self.assertRaises(CloudifyClientError):
            self.client.deployment_updates.update_with_existing_blueprint(
                environment.id, 'updated_basic')

    def test_uninstall_environment_and_parent(self):
        environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment.id, DeploymentState.GOOD
        )
        deployment = self._deploy_deployment_to_environment(
            environment,
            'dsl/simple_deployment.yaml',
            'environment',
            install=True
        )
        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=1
        )
        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=deployment.id,
                              wait_for_execution=True)
        self.delete_deployment(deployment.id, validate=True)

        self._verify_statuses_and_count_for_deployment(
            environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_count=0
        )
        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=environment.id,
                              wait_for_execution=True)
        self.delete_deployment(environment.id, validate=True)

    def test_environment_with_two_levels(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        self._deploy_environment_with_two_levels(main_environment)
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_environments_count=4,
            sub_services_count=2
        )

    def test_environment_with_three_levels(self):
        # Main parent
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        self._deploy_environment_with_three_levels(main_environment)
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_environments_count=6,
            sub_services_count=4
        )

    def test_environment_with_delete_child(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )

        service, environment =  \
            self._deploy_environment_with_service_and_environment(
                main_environment
            )
        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=service.id)
        self.delete_deployment(service.id, validate=True)
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=1
        )

    def test_environment_with_uninstall_child(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )

        service, environment = \
            self._deploy_environment_with_service_and_environment(
                main_environment
            )
        self.execute_workflow(workflow_name='uninstall',
                              deployment_id=service.id)
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.REQUIRE_ATTENTION,
            sub_services_status=DeploymentState.REQUIRE_ATTENTION,
            sub_environments_status=DeploymentState.GOOD,
            sub_services_count=1,
            sub_environments_count=1
        )

    def test_environment_after_removing_parent_label(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        service, environment = \
            self._deploy_environment_with_service_and_environment(
                main_environment
            )

        self.client.deployments.update_labels(environment.id, [
            {
                'csys-obj-type': 'environment'
            }
        ])
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=1
        )

    def test_environment_after_conversion_to_service_type(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        service, environment = \
            self._deploy_environment_with_service_and_environment(
                main_environment
            )
        self.client.deployments.update_labels(environment.id, [
            {
                'csys-obj-type': 'service'
            },
            {
                'csys-obj-parent': main_environment.id
            },
        ])
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=2
        )

    def test_environment_after_conversion_to_environment_type(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        service, environment = \
            self._deploy_environment_with_service_and_environment(
                main_environment
            )
        self.client.deployments.update_labels(service.id, [
            {
                'csys-obj-type': 'environment'
            },
            {
                'csys-obj-parent': main_environment.id
            },
        ])
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=2
        )

    def test_environment_with_adding_single_parent_to_group(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        self._create_deployment_group_from_blueprint(
            'dsl/simple_deployment.yaml',
            'grp-blueprint',
            'group1',
            4,
            labels_to_add=[{'csys-obj-parent': main_environment.id}]
        )
        self._execute_workflow_on_group('group1', 'install')
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=4
        )

    def test_environment_with_adding_multiple_parents_to_group(self):
        environment1 = self._deploy_main_environment('dsl/basic.yaml')
        environment2 = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            environment1.id, DeploymentState.GOOD
        )
        self._assert_main_environment_after_installation(
            environment2.id, DeploymentState.GOOD
        )
        self._create_deployment_group_from_blueprint(
            'dsl/simple_deployment.yaml',
            'grp-blueprint',
            'group1',
            4,
            labels_to_add=[{'csys-obj-parent': environment1.id},
                           {'csys-obj-parent': environment2.id}]
        )
        self._execute_workflow_on_group('group1', 'install')
        self._verify_statuses_and_count_for_deployment(
            environment1.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=4
        )
        self._verify_statuses_and_count_for_deployment(
            environment2.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=4
        )

    def test_environment_with_removing_parent_from_group(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        self._create_deployment_group_from_blueprint(
            'dsl/simple_deployment.yaml',
            'grp-blueprint',
            'group1',
            4,
            labels_to_add=[{'csys-obj-parent': main_environment.id}]
        )
        self._execute_workflow_on_group('group1', 'install')
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=4
        )
        self.client.deployment_groups.put('group1', labels=[])
        main_environment = self.client.deployments.get(main_environment.id)
        self._assert_deployment_environment_attr(
            main_environment,
            deployment_status=DeploymentState.GOOD
        )

    def test_environment_after_conversion_to_environment_type_for_group(self):
        main_environment = self._deploy_main_environment('dsl/basic.yaml')
        self._assert_main_environment_after_installation(
            main_environment.id, DeploymentState.GOOD
        )
        self._create_deployment_group_from_blueprint(
            'dsl/simple_deployment.yaml',
            'grp-blueprint',
            'group1',
            4,
            labels_to_add=[{'csys-obj-parent': main_environment.id}]
        )
        self._execute_workflow_on_group('group1', 'install')
        self._verify_statuses_and_count_for_deployment(
            main_environment.id,
            deployment_status=DeploymentState.GOOD,
            sub_services_status=DeploymentState.GOOD,
            sub_services_count=4
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': main_environment.id},
                    {'csys-obj-type': 'environment'}],
        )
        main_environment = self.client.deployments.get(main_environment.id)
        self._assert_deployment_environment_attr(
            main_environment,
            deployment_status=DeploymentState.GOOD,
            sub_environments_status=DeploymentState.GOOD,
            sub_environments_count=4
        )

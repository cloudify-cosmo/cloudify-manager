
from mock import patch

from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.models_states import DeploymentState

from manager_rest.rest.rest_utils import RecursiveDeploymentLabelsDependencies
from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.test.base_test import BaseServerTestCase


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentLabelsDependenciesTest(BaseServerTestCase):

    def _create_deployment_objects(self, parent_name, deployment_type, size):
        for service in range(1, size + 1):
            self.put_deployment_with_labels(
                [
                    {
                        'csys-obj-parent': parent_name
                    },
                    {
                        'csys-obj-type': deployment_type,
                    }
                ],
                resource_id='{0}_{1}_{2}'.format(
                    deployment_type, service, parent_name)
            )

    def _populate_deployment_labels_dependencies(self):
        self.put_mock_deployments('dep_0', 'dep_1')
        self.put_mock_deployments('dep_2', 'dep_3')
        self.put_mock_deployments('dep_4', 'dep_5')

        self.client.deployments.update_labels('dep_0', [
                {
                    'csys-obj-parent': 'dep_1'
                }
            ]
        )

        self.client.deployments.update_labels('dep_2', [
                {
                    'csys-obj-parent': 'dep_3'
                }
            ]
        )

        self.client.deployments.update_labels('dep_4', [
                {
                    'csys-obj-parent': 'dep_5'
                }
            ]
        )

    @patch('manager_rest.resource_manager.ResourceManager'
           '.handle_deployment_labels_graph')
    @patch('manager_rest.resource_manager.ResourceManager'
           '.verify_attaching_deployment_to_parents')
    def test_deployment_with_empty_labels(self,
                                          verify_parents_mock,
                                          handle_labels_graph_mock):
        self.put_deployment('deployment_with_no_labels')
        verify_parents_mock.assert_not_called()
        handle_labels_graph_mock.assert_not_called()

    @patch('manager_rest.resource_manager.ResourceManager'
           '.handle_deployment_labels_graph')
    @patch('manager_rest.resource_manager.ResourceManager'
           '.verify_attaching_deployment_to_parents')
    def test_deployment_with_non_parent_labels(self,
                                               verify_parents_mock,
                                               handle_labels_graph_mock):
        self.put_deployment_with_labels([{'env': 'aws'}, {'arch': 'k8s'}])
        verify_parents_mock.assert_not_called()
        handle_labels_graph_mock.assert_not_called()

    def test_deployment_with_single_parent_label(self):
        self.put_deployment('parent')
        self.put_deployment_with_labels([{'csys-obj-parent': 'parent'}])

        # deployment response
        deployment = self.client.deployments.get('parent')
        self.assertEqual(deployment.sub_services_count, 1)
        self.assertEqual(deployment.sub_environments_count, 0)

    def test_upload_blueprint_with_invalid_parent_id_on_dsl(self):
        with self.assertRaisesRegex(
                CloudifyClientError,
                'using label `csys-obj-parent` that does not exist'):
            self.put_blueprint(
                blueprint_id='bp1',
                blueprint_file_name='blueprint_with_invalid_parent_labels.yaml'
            )

    def test_upload_blueprint_with_valid_parent_id_on_dsl(self):
        self.put_deployment('valid-id')
        self.put_blueprint(
            blueprint_id='bp1',
            blueprint_file_name='blueprint_with_valid_parent_labels.yaml'
        )

    def test_deployment_with_multiple_parent_labels(self):
        self.put_deployment(deployment_id='parent_1',
                            blueprint_id='blueprint_1')
        self.put_deployment(deployment_id='parent_2',
                            blueprint_id='blueprint_2')
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-parent': 'parent_1'
                },
                {
                    'csys-obj-parent': 'parent_2'
                }
            ]
        )
        deployment_1 = self.client.deployments.get('parent_1')
        deployment_2 = self.client.deployments.get('parent_2')
        self.assertEqual(deployment_1.sub_services_count, 1)
        self.assertEqual(deployment_1.sub_environments_count, 0)
        self.assertEqual(deployment_2.sub_services_count, 1)
        self.assertEqual(deployment_2.sub_environments_count, 0)

    def test_deployment_with_invalid_parent_label(self):
        error_message = 'label `csys-obj-parent` that does not exist'
        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.put_deployment_with_labels(
                [
                    {
                        'csys-obj-parent': 'notexist'
                    }
                ],
                resource_id='invalid_label_dep'
            )

    def test_deployment_with_valid_and_invalid_parent_labels(self):
        self.put_deployment(deployment_id='parent_1')
        error_message = 'label `csys-obj-parent` that does not exist'
        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.put_deployment_with_labels(
                [
                    {
                        'csys-obj-parent': 'parent_1'
                    },
                    {
                        'csys-obj-parent': 'notexist'
                    }
                ],
                resource_id='invalid_label_dep'
            )

    def test_add_valid_label_parent_to_created_deployment(self):
        self.put_deployment(deployment_id='parent_1',
                            blueprint_id='blueprint_1')
        self.put_deployment(deployment_id='parent_2',
                            blueprint_id='blueprint_2')
        self.put_deployment_with_labels([{'csys-obj-parent': 'parent_1'}],
                                        resource_id='label_dep')

        self.client.deployments.update_labels('label_dep', [
                {
                    'csys-obj-parent': 'parent_1'
                },
                {
                    'csys-obj-parent': 'parent_2'
                }
            ]
        )
        deployment_1 = self.client.deployments.get('parent_1')
        deployment_2 = self.client.deployments.get('parent_2')
        self.assertEqual(deployment_1.sub_services_count, 1)
        self.assertEqual(deployment_1.sub_environments_count, 0)
        self.assertEqual(deployment_2.sub_services_count, 1)
        self.assertEqual(deployment_2.sub_environments_count, 0)

    def test_add_invalid_label_parent_to_created_deployment(self):
        error_message = 'label `csys-obj-parent` that does not exist'
        self.put_deployment(deployment_id='parent_1',
                            blueprint_id='blueprint_1')
        self.put_deployment_with_labels([{'csys-obj-parent': 'parent_1'}],
                                        resource_id='invalid_label_dep')

        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.client.deployments.update_labels('invalid_label_dep', [
                    {
                        'csys-obj-parent': 'parent_1'
                    },
                    {
                        'csys-obj-parent': 'notexist'
                    }
                ]
            )

    def test_cyclic_dependencies_between_deployments(self):
        error_message = 'cyclic deployment-labels dependencies.'
        self.put_deployment(deployment_id='deployment_1',
                            blueprint_id='deployment_1')
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-parent': 'deployment_1'
                }
            ],
            resource_id='deployment_2'
        )
        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.client.deployments.update_labels('deployment_1', [
                {
                    'csys-obj-parent': 'deployment_2'
                }
            ])

        deployment_1 = self.client.deployments.get('deployment_1')
        deployment_2 = self.client.deployments.get('deployment_2')
        self.assertEqual(deployment_1.sub_services_count, 1)
        self.assertEqual(deployment_2.sub_services_count, 0)
        self.assertEqual(len(deployment_1.labels), 1)

    def test_number_of_direct_services_deployed_inside_environment(self):
        self.put_deployment(deployment_id='env',
                            blueprint_id='env')
        self._create_deployment_objects('env', 'service', 2)
        deployment = self.client.deployments.get(
            'env', all_sub_deployments=False)
        self.assertEqual(deployment.sub_services_count, 2)

    def test_number_of_total_services_deployed_inside_environment(self):
        self.put_deployment(deployment_id='env',
                            blueprint_id='env')
        self._create_deployment_objects('env', 'service', 2)
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-parent': 'env'
                },
                {
                    'csys-obj-type': 'environment',
                }
            ],
            resource_id='env_1'
        )

        self._create_deployment_objects('env_1', 'service', 2)
        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_services_count, 4)
        deployment = self.client.deployments.get('env',
                                                 all_sub_deployments=False)
        self.assertEqual(deployment.sub_services_count, 2)

    def test_number_of_direct_environments_deployed_inside_environment(self):
        self.put_deployment(deployment_id='env',
                            blueprint_id='env')
        self._create_deployment_objects('env', 'environment', 2)
        deployment = self.client.deployments.get(
            'env', all_sub_deployments=False)
        self.assertEqual(deployment.sub_environments_count, 2)

    def test_number_of_total_environments_deployed_inside_environment(self):
        self.put_deployment(deployment_id='env',
                            blueprint_id='env')
        self._create_deployment_objects('env', 'environment', 2)
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-parent': 'env'
                },
                {
                    'csys-obj-type': 'environment',
                }
            ],
            resource_id='env_1'
        )

        self._create_deployment_objects('env_1', 'environment', 2)
        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_environments_count, 5)
        deployment = self.client.deployments.get('env',
                                                 all_sub_deployments=False)
        self.assertEqual(deployment.sub_environments_count, 3)

    def test_add_sub_deployments_after_deployment_update(self):
        _, _, _, deployment = self.put_deployment(
            deployment_id='env',
            blueprint_id='env'
        )
        _, _, _, deployment_1 = self.put_deployment(
            deployment_id='env_1',
            blueprint_id='env_1'
        )

        self.assertEqual(deployment.sub_services_count, 0)
        self.assertEqual(deployment.sub_services_count, 0)
        self.assertEqual(deployment_1.sub_environments_count, 0)
        self.assertEqual(deployment_1.sub_environments_count, 0)

        self.put_deployment(deployment_id='sub_srv', blueprint_id='srv')
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-type': 'environment',
                }
            ],
            resource_id='sub_env'
        )

        self.put_blueprint(
            blueprint_id='update_sub_srv',
            blueprint_file_name='blueprint_with_parent_labels.yaml'
        )
        self.put_blueprint(
            blueprint_id='update_sub_env',
            blueprint_file_name='blueprint_with_parent_labels.yaml'
        )

        self.client.deployment_updates.update_with_existing_blueprint(
            'sub_srv', blueprint_id='update_sub_srv'
        )
        self.client.deployment_updates.update_with_existing_blueprint(
            'sub_env', blueprint_id='update_sub_env'
        )
        deployment = self.client.deployments.get('env')
        deployment_1 = self.client.deployments.get('env_1')
        self.assertEqual(deployment.sub_services_count, 1)
        self.assertEqual(deployment.sub_services_count, 1)
        self.assertEqual(deployment_1.sub_environments_count, 1)
        self.assertEqual(deployment_1.sub_environments_count, 1)

    def test_detach_all_services_from_deployment(self):
        self.put_deployment(
            deployment_id='env',
            blueprint_id='env'
        )
        self._create_deployment_objects('env', 'service', 2)
        self._create_deployment_objects('env', 'environment', 2)

        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_services_count, 2)
        self.assertEqual(deployment.sub_environments_count, 2)

        self.client.deployments.update_labels(
            'service_1_env',
            [
                {
                    'csys-obj-type': 'service'
                },

            ]
        )
        self.client.deployments.update_labels(
            'service_2_env',
            [
                {
                    'csys-obj-type': 'service'
                },

            ]
        )

        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_services_count, 0)
        self.assertEqual(deployment.sub_environments_count, 2)

    def test_detach_all_environments_from_deployment(self):
        self.put_deployment(
            deployment_id='env',
            blueprint_id='env'
        )
        self._create_deployment_objects('env', 'service', 2)
        self._create_deployment_objects('env', 'environment', 2)

        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_services_count, 2)
        self.assertEqual(deployment.sub_environments_count, 2)

        self.client.deployments.update_labels(
            'environment_1_env',
            [
                {
                    'csys-obj-type': 'environment'
                }
            ]
        )
        self.client.deployments.update_labels(
            'environment_2_env',
            [
                {
                    'csys-obj-type': 'environment'
                }
            ]
        )

        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_services_count, 2)
        self.assertEqual(deployment.sub_environments_count, 0)

    def test_deployment_statuses_after_creation_without_sub_deployments(self):
        self.put_deployment('dep1')
        deployment = self.client.deployments.get('dep1')
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )
        self.assertIsNone(deployment.sub_services_status)
        self.assertIsNone(deployment.sub_environments_status)

    def test_deployment_statuses_after_creation_with_sub_deployments(self):
        self.put_deployment('parent')
        self._create_deployment_objects('parent', 'environment', 2)
        self._create_deployment_objects('parent', 'service', 2)
        deployment = self.client.deployments.get('parent')
        self.assertEqual(
            deployment.deployment_status,
            DeploymentState.REQUIRE_ATTENTION
        )
        self.assertEqual(
            deployment.sub_environments_status,
            DeploymentState.REQUIRE_ATTENTION
        )
        self.assertEqual(
            deployment.sub_services_status,
            DeploymentState.REQUIRE_ATTENTION
        )

    def test_delete_deployment_with_sub_deployments(self):
        self.put_deployment('parent')
        self._create_deployment_objects('parent', 'service', 2)
        with self.assertRaisesRegex(
                CloudifyClientError, 'Can\'t delete deployment'):
            self.client.deployments.delete('parent')

    def test_stop_deployment_with_sub_deployments(self):
        self.put_deployment('parent')
        self._create_deployment_objects('parent', 'service', 2)
        with self.assertRaisesRegex(
                CloudifyClientError, 'Can\'t execute workflow `stop`'):
            self.client.executions.start('parent', 'stop')

    def test_uninstall_deployment_with_sub_deployments(self):
        self.put_deployment('parent')
        self._create_deployment_objects('parent', 'service', 2)
        with self.assertRaisesRegex(
                CloudifyClientError, 'Can\'t execute workflow `uninstall`'):
            self.client.executions.start('parent', 'uninstall')

    def test_create_deployment_labels_dependencies_graph(self):
        self._populate_deployment_labels_dependencies()
        dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        self.assertEqual(dep_graph.graph['dep_1'], {'dep_0'})
        self.assertEqual(dep_graph.graph['dep_3'], {'dep_2'})
        self.assertEqual(dep_graph.graph['dep_5'], {'dep_4'})

    def test_add_to_deployment_labels_dependencies_graph(self):
        self._populate_deployment_labels_dependencies()
        dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        dep_graph.add_dependency_to_graph('dep_00', 'dep_1')
        dep_graph.add_dependency_to_graph('dep_1', 'dep_6')
        self.assertEqual(dep_graph.graph['dep_1'], {'dep_0', 'dep_00'})
        self.assertEqual(dep_graph.graph['dep_6'], {'dep_1'})

    def test_remove_deployment_labels_dependencies_from_graph(self):
        self._populate_deployment_labels_dependencies()
        dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        dep_graph.remove_dependency_from_graph('dep_0', 'dep_1')
        self.assertNotIn('dep_1', dep_graph.graph)

    def test_find_recursive_deployments_from_graph(self):
        self._populate_deployment_labels_dependencies()

        self.client.deployments.update_labels('dep_0', [
                {
                    'csys-obj-parent': 'dep_1'
                }
            ]
        )

        self.put_deployment(deployment_id='dep_11', blueprint_id='dep_11')
        self.put_deployment(deployment_id='dep_12', blueprint_id='dep_12')
        self.put_deployment(deployment_id='dep_13', blueprint_id='dep_13')
        self.put_deployment(deployment_id='dep_14', blueprint_id='dep_14')

        self.client.deployments.update_labels('dep_1', [
                {
                    'csys-obj-parent': 'dep_11'
                }
            ]
        )

        self.client.deployments.update_labels('dep_11', [
                {
                    'csys-obj-parent': 'dep_12'
                }
            ]
        )

        self.client.deployments.update_labels('dep_12', [
                {
                    'csys-obj-parent': 'dep_13'
                }
            ]
        )

        self.client.deployments.update_labels('dep_13', [
                {
                    'csys-obj-parent': 'dep_14'
                }
            ]
        )
        dep_graph = RecursiveDeploymentLabelsDependencies(self.sm)
        dep_graph.create_dependencies_graph()
        targets = dep_graph.find_recursive_deployments(['dep_0'])
        self.assertEqual(len(targets), 5)
        self.assertIn('dep_1', targets)
        self.assertIn('dep_11', targets)
        self.assertIn('dep_12', targets)
        self.assertIn('dep_13', targets)
        self.assertIn('dep_14', targets)

    def test_sub_deployments_counts_after_convert_to_service(self):
        self.put_deployment(deployment_id='env',
                            blueprint_id='env')

        self._create_deployment_objects('env', 'environment', 2)
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-parent': 'env'
                },
                {
                    'csys-obj-type': 'environment',
                }
            ],
            resource_id='env_1'
        )
        self._create_deployment_objects('env_1', 'environment', 2)
        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_environments_count, 5)

        # Remove the csys-obj-type and convert it to service instead
        self.client.deployments.update_labels('env_1', [
                {
                    'csys-obj-parent': 'env'
                }
            ]
        )
        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_environments_count, 4)
        self.assertEqual(deployment.sub_services_count, 1)

    def test_sub_deployments_counts_after_convert_to_environment(self):
        self.put_deployment(deployment_id='env',
                            blueprint_id='env')

        self._create_deployment_objects('env', 'environment', 2)
        self.put_deployment_with_labels(
            [
                {
                    'csys-obj-parent': 'env'
                }
            ],
            resource_id='srv_1'
        )
        self._create_deployment_objects('srv_1', 'service', 2)
        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_environments_count, 2)
        self.assertEqual(deployment.sub_services_count, 3)

        # Add the csys-obj-type and convert it to environment instead
        self.client.deployments.update_labels('srv_1', [
            {
                'csys-obj-parent': 'env'
            },
            {
                'csys-obj-type': 'environment'
            }
        ]
                                              )
        deployment = self.client.deployments.get('env')
        self.assertEqual(deployment.sub_environments_count, 3)
        self.assertEqual(deployment.sub_services_count, 2)

from datetime import datetime

from cloudify_rest_client.exceptions import CloudifyClientError
from manager_rest import manager_exceptions
from manager_rest.storage import models
from manager_rest.test import _assertDictContainsSubset
from manager_rest.test.infrastructure.base_list_test import BaseListTest

TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.3'
OLD_TEST_PACKAGE_VERSION = '1.2'


class ResourceListFiltersTestCase(BaseListTest):

    def setUp(self):
        super(ResourceListFiltersTestCase, self).setUp()
        self.deployments = self._put_n_deployments(
          id_prefix='test', number_of_deployments=2)
        self.first_blueprint_id = 'test0_blueprint'
        self.first_deployment_id = 'test0_deployment'
        self.sec_blueprint_id = 'test1_blueprint'
        self.sec_deployment_id = 'test1_deployment'
        self._put_n_snapshots(number_of_snapshots=2)
        self.first_snapshot_id = 'oh-snap0'
        self.sec_snapshot_id = 'oh-snap1'

    def test_deployments_list_with_filters(self):
        filter_fields = {'id': self.first_deployment_id,
                         'blueprint_id': self.first_blueprint_id}
        response = self.client.deployments.list(**filter_fields)

        self.assertEqual(len(response), 1, 'expecting 1 deployment result, '
                                           'got {0}'.format(len(response)))
        _assertDictContainsSubset(filter_fields, response[0])

    def test_deployments_list_with_filters_multiple_values(self):
        filter_fields = \
            {'id': [self.first_deployment_id, self.sec_deployment_id]}
        self._test_multiple_values_filter('deployments',
                                          filter_fields,
                                          2)

    def test_deployments_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.deployments.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Deployment.resource_fields,
                                            e)

    def test_deployments_list_no_filters(self):
        items = self.client.deployments.list().items
        self.assertEqual(2, len(items), 'expecting 2 deployment results, '
                                        'got {0}'.format(len(items)))

        if items[0]['id'] != self.first_deployment_id:
            items[0], items[1] = items[1], items[0]

        self.assertEqual(self.first_blueprint_id,
                         items[0]['blueprint_id'])
        self.assertEqual(self.sec_blueprint_id,
                         items[1]['blueprint_id'])

    def test_nodes_list_with_filters(self):
        filter_params = {'deployment_id': self.first_deployment_id}
        response = self.client.nodes.list(**filter_params)
        self.assertEqual(2, len(response), 'expecting 2 node results, '
                                           'got {0}'.format(len(response)))
        for node in response:
            self.assertEqual(node['deployment_id'], self.first_deployment_id)
            self.assertEqual(node['blueprint_id'], self.first_blueprint_id)

    def test_nodes_list_with_filters_multiple_values(self):
        filter_params = {'deployment_id':
                         [self.first_deployment_id, self.sec_deployment_id]}
        self._test_multiple_values_filter('nodes', filter_params, 4)

    def test_nodes_list_no_filters(self):
        response = self.client.nodes.list()
        self.assertEqual(4, len(response), 'expecting 4 node results, '
                                           'got {0}'.format(len(response)))
        for node in response:
            self.assertIn(node['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(node['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_nodes_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.nodes.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Node.resource_fields, e)

    def test_executions_list_with_filters(self):
        filter_params = {'deployment_id': self.first_deployment_id,
                         '_include_system_workflows': True}
        response = self.client.executions.list(**filter_params)
        self.assertEqual(1, len(response), 'expecting 1 execution results, '
                                           'got {0}'.format(len(response)))
        execution = response[0]
        self.assertEqual(execution['deployment_id'], self.first_deployment_id)
        self.assertEqual(execution['status'], 'terminated')

    def test_executions_list_with_hybrid_field_filter(self):
        filter_params = {'status_display': 'completed'}
        response = self.client.executions.list(**filter_params)
        self.assertEqual(4, len(response), 'expecting 4 execution results, '
                                           'got {0}'.format(len(response)))
        for execution in response:
            self.assertEqual(execution['status'], 'terminated')
        deployment_ids = [ex['deployment_id'] for ex in response]
        self.assertIn(self.first_deployment_id, deployment_ids)
        self.assertIn(self.sec_deployment_id, deployment_ids)

    def test_executions_list_with_filters_multiple_values(self):
        filter_params = {'deployment_id':
                         [self.first_deployment_id, self.sec_deployment_id],
                         'workflow_id': 'create_deployment_environment',
                         '_include_system_workflows': True}
        self._test_multiple_values_filter('executions', filter_params, 2)

    def test_executions_list_no_filters(self):
        response = self.client.executions.list()
        self.assertEqual(4, len(response), 'expecting 4 executions results, '
                                           'got {0}'.format(len(response)))
        response_no_blueprint_upload = \
            [ex for ex in response if ex['workflow_id'] != 'upload_blueprint']
        for execution in response_no_blueprint_upload:
            self.assertIn(execution['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(execution['blueprint_id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))
            self.assertEqual(execution['status'], 'terminated')

    def assert_bad_parameter_error(self, fields, e):
        self.assertEqual(400, e.status_code)
        self.assertEqual(
          manager_exceptions.BadParametersError.error_code, e.error_code)
        for filter_val in fields:
            self.assertIn(filter_val,
                          str(e),
                          'expecting available filter names be contained '
                          'in error message {0}'.format(e))

    def test_executions_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.executions.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Execution.resource_fields,
                                            e)

    def test_node_instances_list_no_filters(self):
        response = self.client.node_instances.list()
        self.assertEqual(4, len(response), 'expecting 4 node instance results,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertIn(node_instance['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertEqual(node_instance['state'], 'uninitialized')
            self.assertEqual(node_instance['index'], 1)

    def test_node_instances_list_with_filters(self):
        filter_params = {'deployment_id': self.first_deployment_id}
        response = self.client.node_instances.list(**filter_params)
        self.assertEqual(2, len(response), 'expecting 2 node instance results,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertEqual(node_instance['deployment_id'],
                             self.first_deployment_id)
            self.assertEqual(node_instance['state'], 'uninitialized')

    def test_node_instances_list_with_filters_multiple_values(self):
        filter_fields = {'deployment_id': [self.first_deployment_id,
                                           self.sec_deployment_id]}
        self._test_multiple_values_filter('node_instances', filter_fields, 4)

    def test_node_instances_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.node_instances.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(
                models.NodeInstance.resource_fields, e)

    # special parameter 'node_name' is converted to 'node_id' on the server
    def test_node_instances_list_with_node_name_filter(self):
        filter_params = {'node_name': 'http_web_server'}
        response = self.client.node_instances.list(**filter_params)
        self.assertEqual(2, len(response), 'expecting 1 node instance result,'
                                           ' got {0}'.format(len(response)))
        for node_instance in response:
            self.assertIn(node_instance['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertEqual(node_instance['state'], 'uninitialized')

    def test_deployment_modifications_list_no_filters(self):
        for dep in self.deployments:
            self._put_deployment_modification(dep)
        response = self.client.deployment_modifications.list()
        self.assertEqual(2, len(response), 'expecting 2 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))
        for modification in response:
            self.assertIn(modification['deployment_id'],
                          (self.first_deployment_id, self.sec_deployment_id))
            self.assertIn(modification['status'], ('finished', 'started'))

    def test_deployment_modifications_list_with_filters(self):
        for dep in self.deployments:
            self._put_deployment_modification(dep)
        filter_params = {'deployment_id': self.first_deployment_id}
        response = self.client.deployment_modifications.list(**filter_params)
        self.assertEqual(1, len(response), 'expecting 1 deployment mod '
                                           'results, got {0}'
                         .format(len(response)))
        modification = response[0]
        _assertDictContainsSubset(filter_params, modification)
        self.assertEqual(modification['status'], 'finished')

    def test_deployment_modifications_list_with_filters_multiple_values(self):
        for dep in self.deployments:
            self._put_deployment_modification(dep)
        filter_fields = {'deployment_id': [self.first_deployment_id,
                                           self.sec_deployment_id]}
        self._test_multiple_values_filter('deployment_modifications',
                                          filter_fields,
                                          2)

    def test_deployment_modifications_list_non_existent_filters(self):
        for dep in self.deployments:
            self._put_deployment_modification(dep)
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.deployment_modifications.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(
                models.DeploymentModification.resource_fields, e)

    def test_blueprints_list_with_filters(self):
        filter_params = {'id': self.first_blueprint_id}
        response = self.client.blueprints.list(**filter_params)
        self.assertEqual(1, len(response), 'expecting 1 blueprint result,'
                                           ' got {0}'.format(len(response)))
        blueprint = response[0]
        _assertDictContainsSubset(filter_params, blueprint)
        self.assertEqual(self.first_blueprint_id, blueprint['id'])

    def test_blueprints_list_with_filters_multiple_values(self):

        filter_fields = \
            {'id': [self.first_blueprint_id, self.sec_blueprint_id]}
        self._test_multiple_values_filter('blueprints',
                                          filter_fields,
                                          2)

    def test_blueprints_list_no_filters(self):
        response = self.client.blueprints.list()
        self.assertEqual(2, len(response), 'expecting 2 blueprint result,'
                                           ' got {0}'.format(len(response)))
        for blueprint in response:
            self.assertIn(blueprint['id'],
                          (self.first_blueprint_id, self.sec_blueprint_id))

    def test_blueprints_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.blueprints.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Blueprint.resource_fields,
                                            e)

    def test_plugins_list_with_filters(self):
        models.Plugin(
            id='plug1',
            package_name=TEST_PACKAGE_NAME,
            package_version=TEST_PACKAGE_VERSION,
            archive_name='',
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        second_plugin = models.Plugin(
            id='plug2',
            package_name=TEST_PACKAGE_NAME,
            package_version=OLD_TEST_PACKAGE_VERSION,
            archive_name='',
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        filter_field = {'id': second_plugin.id}
        response = self.client.plugins.list(**filter_field)

        self.assertEqual(len(response), 1, 'expecting 1 plugin result, '
                                           'got {0}'.format(len(response)))
        _assertDictContainsSubset(filter_field, response[0])

    def test_plugins_list_non_existing_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.plugins.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(models.Plugin.resource_fields, e)

    def test_plugins_list_no_filters(self):
        first_plugin = models.Plugin(
            id='plug1',
            package_name=TEST_PACKAGE_NAME,
            package_version=TEST_PACKAGE_VERSION,
            archive_name='',
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        second_plugin = models.Plugin(
            id='plug2',
            package_name=TEST_PACKAGE_NAME,
            package_version=OLD_TEST_PACKAGE_VERSION,
            archive_name='',
            uploaded_at=datetime.utcnow(),
            wheels=[],
            creator=self.user,
            tenant=self.tenant,
        )
        response = self.client.plugins.list()
        self.assertEqual(2, len(response), 'expecting 2 plugin results, '
                                           'got {0}'.format(len(response)))

        for plugin in response:
            self.assertIn(plugin['id'], {first_plugin.id, second_plugin.id})
            self.assertIn(
                plugin['uploaded_at'],
                {first_plugin.uploaded_at, second_plugin.uploaded_at}
            )

    def _test_multiple_values_filter(self, resource,
                                     filter_fields, expected_count):
        if not hasattr(self.client, resource):
            raise KeyError("resource {0} doesn't exist".format(resource))
        response = getattr(self.client, resource).list(**filter_fields)
        self.assertEqual(len(response), expected_count,
                         'expecting {0} {1}'
                         ' results, '
                         'got {2}'.format(expected_count,
                                          resource,
                                          len(response)))

        for field in filter_fields:
            if field.startswith('_'):
                continue
            requested_values = filter_fields[field]
            if not isinstance(requested_values, list):
                requested_values = [requested_values]
            retrieved_values = \
                [element[field] for element in response]
            for value in requested_values:
                self.assertIn(value,
                              retrieved_values,
                              'expecting filtered results containing '
                              '{0}={1}, got {2}'
                              .format(field, value, retrieved_values))

    def test_snapshots_list_no_filters(self):
        response = self.client.snapshots.list()
        self.assertEqual(2, len(response), 'expecting 2 snapshot results,'
                                           ' got {0}'.format(len(response)))
        for snapshot in response:
            self.assertIn(snapshot['id'],
                          (self.first_snapshot_id, self.sec_snapshot_id))
            self.assertEqual(snapshot['status'], 'creating')

    def test_snapshots_list_with_filters(self):
        filter_params = {'id': self.first_snapshot_id}
        response = self.client.snapshots.list(**filter_params)
        self.assertEqual(1, len(response), 'expecting 1 snapshot in results,'
                                           ' got {0}'.format(len(response)))
        for snapshot in response:
            self.assertEqual(snapshot['id'], self.first_snapshot_id)
            self.assertEqual(snapshot['status'], 'creating')

    def test_snapshots_list_with_filters_multiple_values(self):
        filter_fields = {'id': [self.first_snapshot_id, self.sec_snapshot_id]}
        self._test_multiple_values_filter('snapshots', filter_fields, 2)

    def test_snapshots_list_non_existent_filters(self):
        filter_fields = {'non_existing_field': 'just_some_value'}
        try:
            self.client.snapshots.list(**filter_fields)
            self.fail('Expecting \'CloudifyClientError\' to be raised')
        except CloudifyClientError as e:
            self.assert_bad_parameter_error(
                models.Snapshot.resource_fields, e)

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.rest.filters_utils import FilterRule


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class SearchesTestCase(base_test.BaseServerTestCase):
    LABELS = [{'key1': 'val1'}, {'key1': 'val2'}, {'key2': 'val3'}]
    LABELS_2 = [{'key1': 'val1'}, {'key1': 'val3'}, {'key3': 'val3'}]
    LABELS_3 = [{'key2': 'val4'}, {'key1': 'val3'}]

    FILTER_RULES = [FilterRule('key1', ['val1'], 'any_of', 'label'),
                    FilterRule('key2', [], 'is_not_null', 'label')]

    def test_list_deployments_with_filter_rules(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        deployments = self.client.deployments.list(
            filter_rules=self.FILTER_RULES)
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0], dep1)
        self.assert_metadata_filtered(deployments, 1)

    def test_list_deployments_with_filter_rules_upper(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        deployments = self.client.deployments.list(
            filter_rules=[FilterRule('KEy1', ['VaL1'], 'any_of', 'label')])
        self.assertEqual(len(deployments), 2)
        self.assert_metadata_filtered(deployments, 0)

    def test_list_deployments_with_filter_rules_and_filter_id(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        dep3 = self.put_deployment_with_labels(self.LABELS_3)
        self._test_list_resources_with_filter_rules_and_filter_id(
            self.client.deployments_filters, self.client.deployments, dep3)

    def test_list_blueprints_with_filter_rules(self):
        for i in range(1, 3):
            bp_file_name = 'blueprint_with_labels_{0}.yaml'.format(i)
            bp_id = 'blueprint_{0}'.format(i)
            self.put_blueprint(blueprint_id=bp_id,
                               blueprint_file_name=bp_file_name)
        all_blueprints = self.client.blueprints.list(
            filter_rules=[
                FilterRule('bp_key1', ['bp_key1_val1'], 'any_of', 'label')])
        second_blueprint = self.client.blueprints.list(
            filter_rules=[
                FilterRule('bp_key2', ['bp_2_val1'], 'any_of', 'label'),
                FilterRule('bp_key1', [], 'is_not_null', 'label')])
        self.assertEqual(len(all_blueprints), 2)
        self.assert_metadata_filtered(all_blueprints, 0)
        self.assertEqual(len(second_blueprint), 1)
        self.assert_metadata_filtered(second_blueprint, 1)

    def test_list_blueprints_with_filter_rules_and_filter_id(self):
        self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp1')
        self.put_blueprint_with_labels(self.LABELS_2, blueprint_id='bp2')
        bp3 = self.put_blueprint_with_labels(self.LABELS_3,
                                             blueprint_id='bp3')
        self._test_list_resources_with_filter_rules_and_filter_id(
            self.client.blueprints_filters, self.client.blueprints, bp3)

    def test_list_deployments_with_duplicate_filter_rules(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        self.create_filter(self.client.deployments_filters, self.FILTER_ID,
                           self.FILTER_RULES)
        deployments = self.client.deployments.list(
            filter_rules=self.FILTER_RULES, filter_id=self.FILTER_ID)
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0], dep1)
        self.assert_metadata_filtered(deployments, 1)

    def _test_list_resources_with_filter_rules_and_filter_id(self,
                                                             filters_client,
                                                             resource_client,
                                                             cmp_resource):
        self.create_filter(filters_client, self.FILTER_ID,
                           [FilterRule('key2', [], 'is_not_null', 'label')])
        resources = resource_client.list(
            filter_rules=[FilterRule('key1', ['val3'], 'any_of', 'label')],
            filter_id=self.FILTER_ID,
            _include=['id']
        )
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].keys(), {'id'})
        self.assertEqual(resources[0]['id'], cmp_resource['id'])

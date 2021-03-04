from manager_rest.test.attribute import attr
from manager_rest.test import base_test


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class SearchesTestCase(base_test.BaseServerTestCase):
    LABELS = [{'env': 'aws'}, {'arch': 'k8s'}]
    LABELS_2 = [{'env': 'gcp'}, {'arch': 'k8s'}]
    FILTER_ID = 'filter'
    FILTER_RULES = [{'key': 'env', 'values': ['aws'],
                     'operator': 'not_any_of', 'type': 'label'},
                    {'key': 'arch', 'values': ['k8s'],
                     'operator': 'any_of', 'type': 'label'}]

    FILTER_RULES_2 = [{'key': 'env', 'values': ['aws'],
                       'operator': 'any_of', 'type': 'label'},
                      {'key': 'arch', 'values': ['k8s'],
                       'operator': 'any_of', 'type': 'label'}]

    def test_list_deployments_with_filter_rules(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        deployments = self.client.deployments_search.list(
            filter_rules=self.FILTER_RULES_2)
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0], dep1)
        self.assert_metadata_filtered(deployments, 1)

    def test_list_deployments_with_filter_id(self):
        self.put_deployment_with_labels(self.LABELS)
        dep2 = self.put_deployment_with_labels(self.LABELS_2)
        self.create_filter(self.client.deployments_filters,
                           self.FILTER_ID, self.FILTER_RULES)
        deployments = self.client.deployments_search.list(
            filter_id=self.FILTER_ID)
        self.assertEqual(len(deployments), 1)
        self.assertEqual(deployments[0], dep2)
        self.assert_metadata_filtered(deployments, 1)

    def test_list_deployments_with_filter_rules_upper(self):
        self.put_deployment_with_labels(self.LABELS)
        self.put_deployment_with_labels(self.LABELS_2)
        deployments = self.client.deployments_search.list(
            filter_rules=[{'key': 'aRcH', 'values': ['k8S'],
                           'operator': 'any_of', 'type': 'label'}])
        self.assertEqual(len(deployments), 2)
        self.assert_metadata_filtered(deployments, 0)

    def test_list_blueprints_with_filter_rules(self):
        for i in range(1, 3):
            bp_file_name = 'blueprint_with_labels_{0}.yaml'.format(i)
            bp_id = 'blueprint_{0}'.format(i)
            self.put_blueprint(blueprint_id=bp_id,
                               blueprint_file_name=bp_file_name)
        all_blueprints = self.client.blueprints_search.list(
            filter_rules=[{'key': 'bp_key1', 'values': ['bp_key1_val1'],
                           'operator': 'any_of', 'type': 'label'}])
        second_blueprint = self.client.blueprints_search.list(
            filter_rules=[{'key': 'bp_key2', 'values': ['bp_2_val1'],
                           'operator': 'any_of', 'type': 'label'},
                          {'key': 'bp_key1', 'values': [],
                           'operator': 'is_not_null', 'type': 'label'}])
        self.assertEqual(len(all_blueprints), 2)
        self.assert_metadata_filtered(all_blueprints, 0)
        self.assertEqual(len(second_blueprint), 1)
        self.assert_metadata_filtered(second_blueprint, 1)

    def test_list_blueprints_with_filter_id(self):
        self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp1')
        bp2 = self.put_blueprint_with_labels(self.LABELS_2, blueprint_id='bp2')
        self.create_filter(self.client.deployments_filters,
                           self.FILTER_ID, self.FILTER_RULES)
        blueprints = self.client.blueprints_search.list(
            filter_id=self.FILTER_ID)
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0], bp2)
        self.assert_metadata_filtered(blueprints, 1)

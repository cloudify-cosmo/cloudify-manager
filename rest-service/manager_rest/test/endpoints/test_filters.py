from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.storage import models
from manager_rest.test.attribute import attr
from manager_rest.rest.filters_utils import (FilterRule,
                                             create_filter_rules_list)
from manager_rest.manager_exceptions import BadFilterRule, BadParametersError

FILTER_ID = 'filter'
LABELS_LEGAL_FILTER_RULES = [
    {'key': 'a', 'values': ['b'], 'operator': 'any_of', 'type': 'label'},
    {'key': 'e', 'values': ['f', 'g'], 'operator': 'any_of', 'type': 'label'},
    {'key': 'c', 'values': ['d'], 'operator': 'not_any_of', 'type': 'label'},
    {'key': 'h', 'values': ['i', 'j'], 'operator': 'not_any_of',
     'type': 'label'},
    {'key': 'k', 'values': [], 'operator': 'is_null', 'type': 'label'},
    {'key': 'l', 'values': [], 'operator': 'is_not_null', 'type': 'label'}
]


class FiltersFunctionalityBaseCase(base_test.BaseServerTestCase):
    LABELS = [{'a': 'b'}, {'a': 'z'}, {'c': 'd'}]
    LABELS_2 = [{'a': 'b'}, {'c': 'z'}, {'e': 'f'}]

    def setUp(self, resource_model):
        super().setUp()
        self.resource_model = resource_model

    def _test_labels_filters_applied(self, res_1_id, res_2_id):
        self.assert_filters_applied([('a', ['b'], 'any_of', 'label')],
                                    {res_1_id, res_2_id}, self.resource_model)
        self.assert_filters_applied([('c', ['z'], 'not_any_of', 'label')],
                                    {res_1_id}, self.resource_model)
        self.assert_filters_applied([('a', ['y', 'z'], 'any_of', 'label'),
                                     ('c', ['d'], 'any_of', 'label')],
                                    {res_1_id}, self.resource_model)
        self.assert_filters_applied([('a', ['b'], 'any_of', 'label'),
                                     ('e', [], 'is_not_null', 'label')],
                                    {res_2_id}, self.resource_model)
        self.assert_filters_applied([('a', ['b'], 'any_of', 'label'),
                                     ('e', [], 'is_null', 'label')],
                                    {res_1_id}, self.resource_model)
        self.assert_filters_applied([('a', [], 'is_null', 'label')], set(),
                                    self.resource_model)

    def test_filter_rule_not_dictionary_fails(self):
        with self.assertRaisesRegex(BadFilterRule, 'not a dictionary'):
            create_filter_rules_list(['a'], self.resource_model)

    def test_filter_rule_missing_entry_fails(self):
        with self.assertRaisesRegex(BadFilterRule, 'missing'):
            create_filter_rules_list([{'key': 'key1'}], self.resource_model)

    def test_filter_rule_key_not_text_type_fails(self):
        with self.assertRaisesRegex(BadFilterRule,  'must be a string'):
            err_filter_rule = {'key': 1, 'values': ['b'],
                               'operator': 'any_of', 'type': 'label'}
            create_filter_rules_list([err_filter_rule], self.resource_model)

    def test_filter_rule_value_not_list_fails(self):
        with self.assertRaisesRegex(BadFilterRule,  'must be a list'):
            err_filter_rule = {'key': 'a', 'values': 'b',
                               'operator': 'any_of', 'type': 'label'}
            create_filter_rules_list([err_filter_rule], self.resource_model)

    def test_parse_filter_rules_fails(self):
        err_filter_rules_params = [
            (('a', ['b'], 'bad_operator', 'label'),
             'operator for filtering by labels must be one of'),
            (('a', ['b'], 'is_null', 'label'),
             'list must be empty if the operator'),
            (('a', ['b'], 'is_not_null', 'label'),
             'list must be empty if the operator'),
            (('a', [], 'any_of', 'label'),
             'list must include at least one item if the operator'),
            (('blueprint_id', ['b'], 'bad_operator', 'attribute'),
             'The operator for filtering by attributes must be'),
            (('bad_attribute', ['dep1'], 'any_of', 'attribute'),
             'Allowed attributes to filter deployments|blueprints by are'),
            (('a', ['b'], 'any_of', 'bad_type'),
             'Filter rule type must be one of'),
            (('bad_attribute', ['dep1'], 'any_of', 'bad_type'),
             'Filter rule type must be one of')
        ]
        for params, err_msg in err_filter_rules_params:
            with self.assertRaisesRegex(BadFilterRule, err_msg):
                create_filter_rules_list([FilterRule(*params)],
                                         self.resource_model)

    def test_key_and_value_validation_fails(self):
        err_filter_rules_params = [
            (('a b', ['b'], 'any_of', 'label'), 'filter rule key'),
            (('a', ['b', 'c d'], 'any_of', 'label'),
             'One of the filter rule values')
        ]
        for params, err_msg in err_filter_rules_params:
            with self.assertRaisesRegex(BadParametersError, err_msg):
                create_filter_rules_list([FilterRule(*params)],
                                         self.resource_model)


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class BlueprintsFiltersFunctionalityCase(FiltersFunctionalityBaseCase):
    def setUp(self):
        super().setUp(models.Blueprint)

    def test_labels_filters_applied(self):
        bp_1 = self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp_1')
        bp_2 = self.put_blueprint_with_labels(self.LABELS_2,
                                              blueprint_id='bp_2')
        self._test_labels_filters_applied(bp_1['id'], bp_2['id'])


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentFiltersFunctionalityCase(FiltersFunctionalityBaseCase):
    def setUp(self):
        super().setUp(models.Deployment)

    def test_labels_filters_applied(self):
        self.client.sites.create('site_1')
        self.client.sites.create('other_site')
        dep1 = self.put_deployment_with_labels(self.LABELS,
                                               resource_id='res_1',
                                               site_name='site_1')
        dep2 = self.put_deployment_with_labels(self.LABELS_2,
                                               resource_id='res_2',
                                               site_name='other_site')
        self._test_labels_filters_applied(dep1.id, dep2.id)
        self.assert_filters_applied(
            [('a', ['b'], 'any_of', 'label'),
             ('c', ['y', 'z'], 'not_any_of', 'label')], {dep1.id})

        self.assert_filters_applied(
            [('a', ['b'], 'any_of', 'label'),
             ('blueprint_id', ['res_1', 'res_2'], 'any_of', 'attribute'),
             ('blueprint_id', ['not_bp'], 'not_any_of', 'attribute'),
             ('site_name', ['site'], 'contain', 'attribute')],
            {dep1.id, dep2.id},
        )

        self.assert_filters_applied(
            [('a', ['b'], 'any_of', 'label'),
             ('blueprint_id', ['res_1', 'res_2'], 'not_any_of', 'attribute')],
            set()
        )

        self.assert_filters_applied(
            [('a', ['b'], 'any_of', 'label'),
             ('blueprint_id', ['res'], 'contain', 'attribute')],
            {dep1.id, dep2.id}
        )

        self.assert_filters_applied(
            [('a', ['b'], 'any_of', 'label'),
             ('blueprint_id', ['res_1'], 'contain', 'attribute')],
            {dep1.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site_1'], 'not_contain', 'attribute')],
            {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site_1', 'site_3'], 'not_contain', 'attribute')],
            {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site'], 'start_with', 'attribute')],
            {dep1.id}
        )

        self.assert_filters_applied(
            [('site_name', ['other', 'blah'], 'start_with', 'attribute')],
            {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site'], 'end_with', 'attribute')],
            {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['1', 'blah'], 'end_with', 'attribute')],
            {dep1.id}
        )


# This way we avoid running it too
del FiltersFunctionalityBaseCase


class FiltersBaseCase(base_test.BaseServerTestCase):
    SIMPLE_RULE = [{'key': 'a', 'values': ['b'], 'operator': 'any_of',
                    'type': 'label'}]
    NEW_RULE = [{'key': 'c', 'values': ['d'], 'operator': 'any_of',
                 'type': 'label'}]

    def setUp(self, filters_resource):
        super().setUp()
        self.filters_client = getattr(self.client, filters_resource)

    def test_create_legal_filter(self):
        new_filter = self.create_filter(self.filters_client, FILTER_ID,
                                        LABELS_LEGAL_FILTER_RULES)
        self.assertEqual(new_filter.labels_filter_rules,
                         LABELS_LEGAL_FILTER_RULES)

    def test_list_filters(self):
        for i in range(3):
            self.create_filter(self.filters_client,
                               '{0}{1}'.format(FILTER_ID, i),
                               [{'key': f'a{i}',
                                 'values': [f'b{i}'],
                                 'operator': 'any_of',
                                 'type': 'label'}])
        filters_list = self.filters_client.list()

        self.assertEqual(len(filters_list.items), 3)
        for i in range(3):
            self.assertEqual(filters_list.items[i].labels_filter_rules,
                             [{'key': f'a{i}',
                               'values': [f'b{i}'],
                               'operator': 'any_of',
                               'type': 'label'}])

    def test_list_filters_sort(self):
        filter_ids = ['a_filter', 'c_filter', 'b_filter']
        for filter_id in filter_ids:
            self.create_filter(self.filters_client,
                               filter_id,
                               self.SIMPLE_RULE)

        sorted_asc_filters_list = self.filters_client.list(sort='id')
        self.assertEqual(
            [filter_elem.id for filter_elem in sorted_asc_filters_list],
            sorted(filter_ids)
        )

        sorted_dsc_filters_list = self.filters_client.list(sort='id',
                                                           is_descending=True)
        self.assertEqual(
            [filter_elem.id for filter_elem in sorted_dsc_filters_list],
            sorted(filter_ids, reverse=True)
        )

    def test_filter_create_lowercase(self):
        # This test only handles one case in order to verify an exception is
        # thrown during a filter creation. All cases are tested in the
        # FiltersFunctionalityTest::test_parse_filter_rules_fails test.
        simple_rule_uppercase = [{'key': 'A',
                                  'values': ['B'],
                                  'operator': 'any_of',
                                  'type': 'label'}]
        new_filter = self.create_filter(self.filters_client,
                                        FILTER_ID,
                                        simple_rule_uppercase)
        self.assertEqual(new_filter.labels_filter_rules, self.SIMPLE_RULE)

    def test_filter_create_fails(self):
        err_filter_rule = [{'key': 'a', 'values': 'b', 'operator': 'any_of',
                            'type': 'label'}]
        with self.assertRaisesRegex(CloudifyClientError, 'must be a list'):
            self.create_filter(self.filters_client, FILTER_ID, err_filter_rule)

    def test_create_filter_with_duplicate_filter_rules(self):
        filter_rule = FilterRule('a', ['b'], 'any_of', 'label')
        new_filter = self.create_filter(self.filters_client, FILTER_ID,
                                        [filter_rule, filter_rule])
        self.assertEqual(new_filter.labels_filter_rules, [filter_rule])

    def test_get_filter(self):
        self.create_filter(self.filters_client, FILTER_ID, self.SIMPLE_RULE)
        fetched_filter = self.filters_client.get(FILTER_ID)
        self.assertEqual(fetched_filter.labels_filter_rules, self.SIMPLE_RULE)

    def test_delete_filter(self):
        self.create_filter(self.filters_client, FILTER_ID, self.SIMPLE_RULE)
        self.assertEqual(len(self.filters_client.list().items), 1)
        self.filters_client.delete(FILTER_ID)
        self.assertEqual(len(self.filters_client.list().items), 0)

    def test_update_filter(self):
        self.update_filter(filters_client=self.filters_client,
                           new_filter_rules=self.NEW_RULE,
                           new_visibility=VisibilityState.GLOBAL)

    def test_update_filter_only_visibility(self):
        self.update_filter(filters_client=self.filters_client,
                           new_visibility=VisibilityState.GLOBAL)

    def test_update_filter_only_filter_rules(self):
        self.update_filter(filters_client=self.filters_client,
                           new_filter_rules=self.NEW_RULE)

    def test_update_filter_no_args_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'to update a filter'):
            self.update_filter(filters_client=self.filters_client)

    def test_update_filter_narrower_visibility_fails(self):
        with self.assertRaisesRegex(CloudifyClientError,
                                    'has wider visibility'):
            self.update_filter(filters_client=self.filters_client,
                               new_visibility=VisibilityState.PRIVATE)


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class BlueprintsFiltersCase(FiltersBaseCase):
    def setUp(self):
        super().setUp('blueprints_filters')


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class DeploymentsFiltersCase(FiltersBaseCase):
    def setUp(self):
        super().setUp('deployments_filters')


# This way we avoid running it too
del FiltersBaseCase

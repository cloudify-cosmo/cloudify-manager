from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.storage import models
from manager_rest.test.attribute import attr
from manager_rest.rest.filters_utils import (FilterRule,
                                             create_filter_rules_list)
from manager_rest.constants import AttrsOperator, LabelsOperator
from manager_rest.manager_exceptions import BadFilterRule, BadParametersError

FILTER_ID = 'filter'
LEGAL_FILTER_RULES = [
    FilterRule('a', ['b'], LabelsOperator.ANY_OF, 'label'),
    FilterRule('e', ['f', 'g'], LabelsOperator.ANY_OF, 'label'),
    FilterRule('c', ['d'], LabelsOperator.NOT_ANY_OF, 'label'),
    FilterRule('h', ['i', 'j'], LabelsOperator.NOT_ANY_OF, 'label'),
    FilterRule('k', [], LabelsOperator.IS_NULL, 'label'),
    FilterRule('l', [], LabelsOperator.IS_NOT_NULL, 'label'),
    FilterRule('created_by', ['user'], AttrsOperator.ANY_OF, 'attribute'),
    FilterRule('created_by', ['user', 'admin'], AttrsOperator.ANY_OF,
               'attribute'),
    FilterRule('created_by', ['user'], AttrsOperator.NOT_ANY_OF, 'attribute'),
    FilterRule('created_by', ['user', 'admin'], AttrsOperator.NOT_ANY_OF,
               'attribute'),
    FilterRule('created_by', ['user'], AttrsOperator.CONTAINS, 'attribute'),
    FilterRule('created_by', ['user', 'admin'], AttrsOperator.CONTAINS,
               'attribute'),
    FilterRule('created_by', ['user'], AttrsOperator.NOT_CONTAINS,
               'attribute'),
    FilterRule('created_by', ['user', 'admin'], AttrsOperator.NOT_CONTAINS,
               'attribute'),
    FilterRule('created_by', ['user'], AttrsOperator.STARTS_WITH, 'attribute'),
    FilterRule('created_by', ['user', 'admin'], AttrsOperator.STARTS_WITH,
               'attribute'),
    FilterRule('created_by', ['user'], AttrsOperator.ENDS_WITH, 'attribute'),
    FilterRule('created_by', ['user', 'admin'], AttrsOperator.ENDS_WITH,
               'attribute'),
    FilterRule('created_by', [], AttrsOperator.IS_NOT_EMPTY, 'attribute')
]


class FiltersFunctionalityBaseCase(base_test.BaseServerTestCase):
    LABELS = [{'a': 'b'}, {'a': 'z'}, {'c': 'd'}]
    LABELS_2 = [{'a': 'b'}, {'c': 'z'}, {'e': 'f'}]

    def setUp(self, resource_model):
        super().setUp()
        self.resource_model = resource_model

    def _test_labels_filters_applied(self, res_1_id, res_2_id):
        self.assert_filters_applied([('a', ['b'], LabelsOperator.ANY_OF,
                                      'label')],
                                    {res_1_id, res_2_id}, self.resource_model)
        self.assert_filters_applied([('c', ['z'], LabelsOperator.NOT_ANY_OF,
                                      'label')],
                                    {res_1_id}, self.resource_model)
        self.assert_filters_applied([('a', ['y', 'z'], LabelsOperator.ANY_OF,
                                      'label'),
                                     ('c', ['d'], LabelsOperator.ANY_OF,
                                      'label')],
                                    {res_1_id}, self.resource_model)
        self.assert_filters_applied([('a', ['b'], LabelsOperator.ANY_OF,
                                      'label'),
                                     ('e', [], LabelsOperator.IS_NOT_NULL,
                                      'label')],
                                    {res_2_id}, self.resource_model)
        self.assert_filters_applied([('a', ['b'], LabelsOperator.ANY_OF,
                                      'label'),
                                     ('e', [], LabelsOperator.IS_NULL,
                                      'label')],
                                    {res_1_id}, self.resource_model)
        self.assert_filters_applied([('a', [], LabelsOperator.IS_NULL,
                                      'label')], set(),
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
                               'operator': LabelsOperator.ANY_OF,
                               'type': 'label'}
            create_filter_rules_list([err_filter_rule], self.resource_model)

    def test_filter_rule_value_not_list_fails(self):
        with self.assertRaisesRegex(BadFilterRule,  'must be a list'):
            err_filter_rule = {'key': 'a', 'values': 'b',
                               'operator': LabelsOperator.ANY_OF,
                               'type': 'label'}
            create_filter_rules_list([err_filter_rule], self.resource_model)

    def test_parse_filter_rules_fails(self):
        err_filter_rules_params = [
            (('a', ['b'], 'bad_operator', 'label'),
             'operator for filtering by labels must be one of'),
            (('a', ['b'], LabelsOperator.IS_NULL, 'label'),
             'list must be empty if the operator'),
            (('a', ['b'], LabelsOperator.IS_NOT_NULL, 'label'),
             'list must be empty if the operator'),
            (('a', [], LabelsOperator.ANY_OF, 'label'),
             'list must include at least one item if the operator'),
            (('blueprint_id', ['b'], 'bad_operator', 'attribute'),
             'The operator for filtering by attributes must be'),
            (('bad_attribute', ['dep1'], LabelsOperator.ANY_OF, 'attribute'),
             'Allowed attributes to filter deployments|blueprints by are'),
            (('a', ['b'], LabelsOperator.ANY_OF, 'bad_type'),
             'Filter rule type must be one of'),
            (('bad_attribute', ['dep1'], LabelsOperator.ANY_OF, 'bad_type'),
             'Filter rule type must be one of')
        ]
        for params, err_msg in err_filter_rules_params:
            with self.assertRaisesRegex(BadFilterRule, err_msg):
                create_filter_rules_list([FilterRule(*params)],
                                         self.resource_model)

    def test_key_and_value_validation_fails(self):
        err_filter_rules_params = [
            (('a b', ['b'], LabelsOperator.ANY_OF, 'label'),
             'filter rule key'),
            (('a', ['b', 'c d'], LabelsOperator.ANY_OF, 'label'),
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
            [('a', ['b'], LabelsOperator.ANY_OF, 'label'),
             ('c', ['y', 'z'], LabelsOperator.NOT_ANY_OF, 'label')], {dep1.id})

        self.assert_filters_applied(
            [('a', ['b'], LabelsOperator.ANY_OF, 'label'),
             ('blueprint_id', ['res_1', 'res_2'], AttrsOperator.ANY_OF,
              'attribute'),
             ('blueprint_id', ['not_bp'], AttrsOperator.NOT_ANY_OF,
              'attribute'),
             ('site_name', ['site'], AttrsOperator.CONTAINS, 'attribute')],
            {dep1.id, dep2.id},
        )

        self.assert_filters_applied(
            [('a', ['b'], LabelsOperator.ANY_OF, 'label'),
             ('blueprint_id', ['res_1', 'res_2'], AttrsOperator.NOT_ANY_OF,
              'attribute')],
            set()
        )

        self.assert_filters_applied(
            [('a', ['b'], LabelsOperator.ANY_OF, 'label'),
             ('blueprint_id', ['res'], AttrsOperator.CONTAINS, 'attribute')],
            {dep1.id, dep2.id}
        )

        self.assert_filters_applied(
            [('a', ['b'], LabelsOperator.ANY_OF, 'label'),
             ('blueprint_id', ['res_1'], AttrsOperator.CONTAINS, 'attribute')],
            {dep1.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site_1'], AttrsOperator.NOT_CONTAINS,
              'attribute')], {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site_1', 'site_3'], AttrsOperator.NOT_CONTAINS,
              'attribute')], {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site'], AttrsOperator.STARTS_WITH, 'attribute')],
            {dep1.id}
        )

        self.assert_filters_applied(
            [('site_name', ['other', 'blah'], AttrsOperator.STARTS_WITH,
              'attribute')], {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['site'], AttrsOperator.ENDS_WITH, 'attribute')],
            {dep2.id}
        )

        self.assert_filters_applied(
            [('site_name', ['1', 'blah'], AttrsOperator.ENDS_WITH,
              'attribute')], {dep1.id}
        )


# This way we avoid running it too
del FiltersFunctionalityBaseCase


class FiltersBaseCase(base_test.BaseServerTestCase):
    LABELS_RULE = FilterRule('a', ['b'],  LabelsOperator.ANY_OF, 'label')
    ATTRS_RULE = FilterRule('created_by', ['admin'],  AttrsOperator.NOT_ANY_OF,
                            'attribute')
    FILTER_RULES = [LABELS_RULE, ATTRS_RULE]

    NEW_LABELS_RULE = FilterRule('c', ['d'], LabelsOperator.ANY_OF, 'label')
    NEW_ATTRS_RULE = FilterRule('created_by', ['user'], AttrsOperator.ANY_OF,
                                'attribute')
    NEW_RULES = [NEW_LABELS_RULE, NEW_ATTRS_RULE]

    def setUp(self, filters_resource):
        super().setUp()
        self.filters_client = getattr(self.client, filters_resource)

    def test_create_legal_filter(self):
        new_filter = self.create_filter(self.filters_client,
                                        FILTER_ID,
                                        LEGAL_FILTER_RULES)
        self.assertEqual(new_filter.value, LEGAL_FILTER_RULES)

    def test_list_filters(self):
        for i in range(3):
            self.create_filter(self.filters_client,
                               '{0}{1}'.format(FILTER_ID, i),
                               [FilterRule(f'a{i}', [f'b{i}'],
                                           LabelsOperator.ANY_OF, 'label')])
        filters_list = self.filters_client.list()

        self.assertEqual(len(filters_list.items), 3)
        for i in range(3):
            self.assertEqual(filters_list.items[i].labels_filter_rules,
                             [FilterRule(f'a{i}', [f'b{i}'],
                                         LabelsOperator.ANY_OF, 'label')])

    def test_list_filters_sort(self):
        filter_ids = ['a_filter', 'c_filter', 'b_filter']
        for filter_id in filter_ids:
            self.create_filter(self.filters_client,
                               filter_id,
                               self.FILTER_RULES)

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
        simple_rule_uppercase = [FilterRule('A', ['B'], LabelsOperator.ANY_OF,
                                            'label')]
        new_filter = self.create_filter(self.filters_client,
                                        FILTER_ID,
                                        simple_rule_uppercase)
        self.assertEqual(new_filter.value, [self.LABELS_RULE])

    def test_filter_create_fails(self):
        err_filter_rule = [{'key': 'a', 'values': 'b', 'operator': 'any_of',
                            'type': 'label'}]
        with self.assertRaisesRegex(CloudifyClientError, 'must be a list'):
            self.create_filter(self.filters_client, FILTER_ID, err_filter_rule)

    def test_create_filter_with_duplicate_filter_rules(self):
        new_filter = self.create_filter(self.filters_client,
                                        FILTER_ID,
                                        [self.LABELS_RULE, self.ATTRS_RULE,
                                         self.LABELS_RULE, self.ATTRS_RULE])
        self.assertEqual(new_filter.value, self.FILTER_RULES)

    def test_get_filter(self):
        self.create_filter(self.filters_client, FILTER_ID, self.FILTER_RULES)
        fetched_filter = self.filters_client.get(FILTER_ID)
        self.assertEqual(fetched_filter.value, self.FILTER_RULES)

    def test_delete_filter(self):
        self.create_filter(self.filters_client, FILTER_ID, self.FILTER_RULES)
        self.assertEqual(len(self.filters_client.list().items), 1)
        self.filters_client.delete(FILTER_ID)
        self.assertEqual(len(self.filters_client.list().items), 0)

    def test_update_filter(self):
        self._update_filter(new_filter_rules=self.NEW_RULES,
                            new_visibility=VisibilityState.GLOBAL)

    def test_update_filter_only_visibility(self):
        self._update_filter(new_visibility=VisibilityState.GLOBAL)

    def test_update_filter_only_filter_rules(self):
        self._update_filter(new_filter_rules=self.NEW_RULES)

    def test_update_filter_no_args_fails(self):
        with self.assertRaisesRegex(RuntimeError, 'to update a filter'):
            self._update_filter()

    def test_update_filter_narrower_visibility_fails(self):
        with self.assertRaisesRegex(CloudifyClientError,
                                    'has wider visibility'):
            self._update_filter(new_visibility=VisibilityState.PRIVATE)

    def test_update_filter_updates_only_labels_rules(self):
        self._update_filter(new_filter_rules=[self.NEW_LABELS_RULE])

    def test_update_filter_updates_only_attrs_rules(self):
        self._update_filter(new_filter_rules=[self.NEW_ATTRS_RULE])

    def _update_filter(self, new_filter_rules=None, new_visibility=None):
        orig_filter = self.create_filter(self.filters_client,
                                         FILTER_ID,
                                         self.FILTER_RULES)
        updated_filter = self.filters_client.update(FILTER_ID,
                                                    new_filter_rules,
                                                    new_visibility)

        updated_visibility = new_visibility or VisibilityState.TENANT
        if new_filter_rules:
            new_attrs_filter_rules = self._get_filter_rules_by_type(
                new_filter_rules, 'attribute')
            new_labels_filter_rules = self._get_filter_rules_by_type(
                new_filter_rules, 'label')

            if new_attrs_filter_rules:
                if new_labels_filter_rules:
                    updated_rules = new_filter_rules
                else:
                    updated_rules = [self.LABELS_RULE] + new_attrs_filter_rules
            elif new_labels_filter_rules:
                updated_rules = [self.ATTRS_RULE] + new_labels_filter_rules
            else:
                raise Exception('Unknown filter rule type')
        else:
            updated_rules = self.FILTER_RULES

        self.assertEqual(updated_filter.value, updated_rules)
        self.assertEqual(updated_filter.visibility, updated_visibility)
        self.assertGreater(updated_filter.updated_at, orig_filter.updated_at)


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

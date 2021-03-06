from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.constants import (LABEL_LEN, EQUAL, NOT_EQUAL, IS_NULL,
                                    IS_NOT_NULL)
from manager_rest.test.attribute import attr
from manager_rest.storage.models_base import db
from manager_rest.utils import get_filters_list_from_mapping
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.storage.filters import add_labels_filters_to_query
from manager_rest.rest.filters_utils import (BadLabelsFilter,
                                             create_labels_filters_mapping)
from manager_rest.storage.resource_models import Deployment, DeploymentLabel

FILTER_ID = 'filter'
LEGAL_RULES = ['a=b', 'e=[f,g]', 'c!=d', 'h!=[i,j]',
               'k is null', 'l is not null']


class FiltersFunctionalityTest(base_test.BaseServerTestCase):

    LABELS = [{'a': 'b'}, {'a': 'z'}, {'c': 'd'}]
    LABELS_2 = [{'a': 'b'}, {'c': 'z'}, {'e': 'f'}]
    FILTER_RULES = ['a=b', 'p is not null', 'f!=g', 'f!=h', 'c=[d,e]',
                    'f!=[i,j]', 'k!=l', 'm is null', 'n is not null',
                    'o is null']

    def test_create_filters_mapping(self):
        expected_filters_mapping = {
            EQUAL: {
                'a': ['b'],
                'c': ['d', 'e']
            },
            NOT_EQUAL: {
                'f': ['g', 'h', 'i', 'j'],
                'k': ['l']
            },
            IS_NULL: ['m', 'o'],
            IS_NOT_NULL: ['p', 'n']
        }
        filters_mapping = create_labels_filters_mapping(self.FILTER_RULES)
        self.assertEqual(filters_mapping, expected_filters_mapping)

    def test_create_filters_mapping_fails(self):
        with self.assertRaisesRegex(BadParametersError,
                                    '.*have the same key.*'):
            create_labels_filters_mapping(['a=b', 'b!=c', 'a=c'])

    def test_create_filters_list(self):
        created_filters_list = get_filters_list_from_mapping(
            create_labels_filters_mapping(LEGAL_RULES))
        self.assertEqual(set(created_filters_list), set(LEGAL_RULES))

    def test_filters_applied(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        dep2 = self.put_deployment_with_labels(self.LABELS_2)
        self._assert_filters_applied({EQUAL: {'a': ['b']}}, {dep1.id, dep2.id})
        self._assert_filters_applied({NOT_EQUAL: {'c': ['z']}}, {dep1.id})
        self._assert_filters_applied({EQUAL: {'a': ['y', 'z'], 'c': ['d']}},
                                     {dep1.id})
        self._assert_filters_applied({EQUAL: {'a': ['b']}, IS_NOT_NULL: ['e']},
                                     {dep2.id})
        self._assert_filters_applied({EQUAL: {'a': ['b']}, IS_NULL: ['e']},
                                     {dep1.id})
        self._assert_filters_applied({IS_NULL: ['a']}, set())
        self._assert_filters_applied(
            {EQUAL: {'a': ['b']}, NOT_EQUAL: {'c': ['y', 'z']}}, {dep1.id})

    def test_filters_functionality_fails(self):
        err_filters = ['a null', 'a', 'a!b']
        for err_filter in err_filters:
            with self.assertRaisesRegex(BadLabelsFilter,
                                        '.*not in the right format.*'):
                create_labels_filters_mapping([err_filter])

    @staticmethod
    def _assert_filters_applied(filter_labels, deployments_ids_set):
        """Asserts the right deployments return when filter labels are applied

        :param filter_labels: The list of filter labels
        :param deployments_ids_set: The corresponding deployments' IDs set
        """
        query = db.session.query(Deployment)
        query = add_labels_filters_to_query(query,
                                            DeploymentLabel,
                                            filter_labels)
        deployments = query.all()

        assert deployments_ids_set == set(dep.id for dep in deployments)


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
class FiltersTestCase(base_test.BaseServerTestCase):
    SIMPLE_RULE = ['a=b']

    def test_create_legal_filter(self):
        new_filter = self.create_filter(FILTER_ID, LEGAL_RULES)
        self.assertEqual(new_filter.labels_filter, LEGAL_RULES)

    def test_list_filters(self):
        for i in range(3):
            self.create_filter('{0}{1}'.format(FILTER_ID, i),
                               ['a{0}=b{0}'.format(i)])
        filters_list = self.client.filters.list()

        self.assertEqual(len(filters_list.items), 3)
        for i in range(3):
            self.assertEqual(filters_list.items[i].labels_filter,
                             ['a{0}=b{0}'.format(i)])

    def test_list_filters_sort(self):
        filter_names = ['a_filter', 'c_filter', 'b_filter']
        for filter_name in filter_names:
            self.create_filter(filter_name, self.SIMPLE_RULE)

        sorted_asc_filters_list = self.client.filters.list(sort='id')
        self.assertEqual(
            [filter_elem.id for filter_elem in sorted_asc_filters_list],
            sorted(filter_names)
        )

        sorted_dsc_filters_list = self.client.filters.list(
            sort='id', is_descending=True)
        self.assertEqual(
            [filter_elem.id for filter_elem in sorted_dsc_filters_list],
            sorted(filter_names, reverse=True)
        )

    def test_filter_create_lowercase(self):
        legal_rules_uppercase = (
                [rule.upper() for rule in LEGAL_RULES[:4]] +
                ['K is null', 'L is not null'])
        new_filter = self.create_filter(FILTER_ID, legal_rules_uppercase)
        self.assertEqual(new_filter.labels_filter, LEGAL_RULES)

    def test_filter_create_strip(self):
        legal_rules_whitespace = ['a = b', 'c != d', 'e= [f , g]',
                                  'h !=[ i,j ]', 'k is null', 'l is not null']
        new_filter = self.create_filter(FILTER_ID, legal_rules_whitespace)
        self.assertEqual(new_filter.labels_filter, LEGAL_RULES)

    def test_filter_create_fails(self):
        err_rules = [
            (['a={0}'.format('b'*(LABEL_LEN+1))], '.*too long.*'),
            (['a= '], '.*is empty.*'),
            (['a!=b]'], '.*illegal characters.*'),
            (['a'], '.*not in the right format.*'),
            (['a null'], '.*not in the right format.*'),
            (['a=b=c'], '.*not in the right format.*'),
        ]

        for err_rule, err_msg in err_rules:
            with self.assertRaisesRegex(CloudifyClientError, err_msg):
                self.create_filter(FILTER_ID, err_rule)

    def test_get_filter(self):
        self.create_filter(FILTER_ID, self.SIMPLE_RULE)
        fetched_filter = self.client.filters.get(FILTER_ID)
        self.assertEqual(fetched_filter.labels_filter, self.SIMPLE_RULE)

    def test_delete_filter(self):
        self.create_filter(FILTER_ID, ['a=b'])
        self.assertEqual(len(self.client.filters.list().items), 1)
        self.client.filters.delete(FILTER_ID)
        self.assertEqual(len(self.client.filters.list().items), 0)

    def test_update_filter(self):
        self.update_filter(['c=d'], VisibilityState.GLOBAL)

    def test_update_filter_only_visibility(self):
        self.update_filter(new_visibility=VisibilityState.GLOBAL)

    def test_update_filter_only_filter_rules(self):
        self.update_filter(new_filter_rules=['c=d'])

    def test_update_filter_no_args_fails(self):
        with self.assertRaisesRegex(RuntimeError, '.*to update a filter.*'):
            self.update_filter()

    def test_update_filter_narrower_visibility_fails(self):
        with self.assertRaisesRegex(CloudifyClientError,
                                    '.*has wider visibility.*'):
            self.update_filter(new_visibility=VisibilityState.PRIVATE)

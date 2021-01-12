from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.storage.models_base import db
from manager_rest.manager_exceptions import BadParametersError
from manager_rest.rest.resources_v3_1.deployments import LABEL_LEN
from manager_rest.storage.filters import add_labels_filters_to_query
from manager_rest.storage.resource_models import Deployment, DeploymentLabel

FILTER_ID = 'filter'


class FiltersFunctionalityTest(base_test.BaseServerTestCase):

    LABELS = [{'a': 'b'}, {'a': 'z'}, {'c': 'd'}]
    LABELS_2 = [{'a': 'b'}, {'c': 'z'}, {'e': 'f'}]

    def test_filters_functionality(self):
        dep1 = self.put_deployment_with_labels(self.LABELS)
        dep2 = self.put_deployment_with_labels(self.LABELS_2)
        self._assert_filters_applied(['a=b'], {dep1.id, dep2.id})
        self._assert_filters_applied(['c!=z'], {dep1.id})
        self._assert_filters_applied(['a=[y,z]', 'c=d'], {dep1.id})
        self._assert_filters_applied(['e is not null', 'a=b'], {dep2.id})
        self._assert_filters_applied(['e is null', 'a=b'], {dep1.id})
        self._assert_filters_applied(['a is null'], set())
        self._assert_filters_applied(['c!=[y,z]', 'a=b'], {dep1.id})

    def test_filters_functionality_fails(self):
        err_filters = ['a null', 'a', 'a!b']
        for err_filter in err_filters:
            with self.assertRaisesRegex(BadParametersError,
                                        '.*not in the right format.*'):
                query = db.session.query(Deployment)
                add_labels_filters_to_query(
                    query, DeploymentLabel, [err_filter])

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
    LEGAL_RULES = ['a=b', 'c!=d', 'e=[f,g]', 'h!=[i,j]',
                   'k is null', 'l is not null']

    def create_filter(self, filter_name, filter_rules,
                      visibility=VisibilityState.TENANT):
        return self.client.filters.create(
            filter_name, filter_rules, visibility)

    def list_filters(self, **kwargs):
        return self.client.filters.list(**kwargs)

    def update_filter(self, filter_name, new_filter_rules, new_visibility):
        return self.client.filters.update(
            filter_name, new_filter_rules, new_visibility)

    def test_create_legal_filter(self):
        new_filter = self.create_filter(FILTER_ID, self.LEGAL_RULES)
        self.assertEqual(new_filter.labels_filter, self.LEGAL_RULES)

    def test_list_filters(self):
        for i in range(3):
            self.create_filter('{0}{1}'.format(FILTER_ID, i),
                               ['a{0}=b{0}'.format(i)])
        filters_list = self.list_filters()

        self.assertEqual(len(filters_list.items), 3)
        for i in range(3):
            self.assertEqual(filters_list.items[i].labels_filter,
                             ['a{0}=b{0}'.format(i)])

    def test_list_filters_sort(self):
        filter_names = ['c_filter', 'b_filter', 'a_filter']
        for filter_name in filter_names:
            self.create_filter(filter_name, self.SIMPLE_RULE)

        filters_list = self.list_filters(_sort='id')
        filter_names.sort()
        self.assertEqual(
            [filter_elem.id for filter_elem in filters_list.items],
            filter_names
        )

    def test_filter_create_lowercase(self):
        legal_rules_uppercase = (
                [rule.upper() for rule in self.LEGAL_RULES[:4]] +
                ['K is null', 'L is not null'])
        new_filter = self.create_filter(FILTER_ID, legal_rules_uppercase)
        self.assertEqual(new_filter.labels_filter, self.LEGAL_RULES)

    def test_filter_create_strip(self):
        legal_rules_whitespace = ['a = b', 'c != d', 'e= [f , g]',
                                  'h !=[ i,j ]', 'k is null', 'l is not null']
        new_filter = self.create_filter(FILTER_ID, legal_rules_whitespace)
        self.assertEqual(new_filter.labels_filter, self.LEGAL_RULES)

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
        self.assertEqual(len(self.list_filters().items), 1)
        self.client.filters.delete(FILTER_ID)
        self.assertEqual(len(self.list_filters().items), 0)

    def test_update_filter(self):
        self._test_update_filter(['c=d'], VisibilityState.GLOBAL)

    def test_update_filter_only_visibility(self):
        self._test_update_filter(new_visibility=VisibilityState.GLOBAL)

    def test_update_filter_only_filter_rules(self):
        self._test_update_filter(new_filter_rules=['c=d'])

    def test_update_filter_no_args_fails(self):
        with self.assertRaisesRegex(RuntimeError, '.*to update a filter.*'):
            self._test_update_filter()

    def test_update_filter_narrower_visibility_fails(self):
        with self.assertRaisesRegex(CloudifyClientError,
                                    '.*has wider visibility.*'):
            self._test_update_filter(new_visibility=VisibilityState.PRIVATE)

    def _test_update_filter(self, new_filter_rules=None, new_visibility=None):
        orig_filter = self.create_filter(FILTER_ID, self.SIMPLE_RULE)
        self.update_filter(FILTER_ID, new_filter_rules, new_visibility)
        updated_filter = self.client.filters.get(FILTER_ID)

        updated_rules = new_filter_rules or self.SIMPLE_RULE
        updated_visibility = new_visibility or VisibilityState.TENANT
        self.assertEqual(updated_filter.labels_filter, updated_rules)
        self.assertEqual(updated_filter.visibility, updated_visibility)
        self.assertGreater(updated_filter.updated_at, orig_filter.updated_at)

from manager_rest.test import base_test
from manager_rest.storage.models_base import db
from manager_rest.storage.filters import add_labels_filters_to_query
from manager_rest.storage.resource_models import Deployment, DeploymentLabel


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

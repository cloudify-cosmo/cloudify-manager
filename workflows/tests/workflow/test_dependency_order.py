__author__ = 'ran'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy


class TestDependencyOrder(TestCase):
    def test_dependencies_order_with_two_nodes(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        deploy(dsl_path)

        from cosmo.testmockoperations.tasks import get_state as testmock_get_state
        states = testmock_get_state.apply_async().get(timeout=10)
        self.assertEquals(2, len(states))
        self.assertEquals('mock_app.containing_node', states[0]['id'])
        self.assertEquals('mock_app.contained_in_node', states[1]['id'])
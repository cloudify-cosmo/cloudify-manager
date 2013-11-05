__author__ = 'ran'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy


class TestDependencyOrder(TestCase):
    def test_dependencies_order_with_two_nodes(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        deploy(dsl_path)

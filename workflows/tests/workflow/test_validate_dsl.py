__author__ = 'ran'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import validate_dsl as validate


class TestValidateDSL(TestCase):

    def test_ok_dsl(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        validate(dsl_path)

    def test_invalid_dsl(self):
        dsl_path = resource("dsl/invalid-dsl.yaml")
        self.assertRaises(RuntimeError, validate, dsl_path)

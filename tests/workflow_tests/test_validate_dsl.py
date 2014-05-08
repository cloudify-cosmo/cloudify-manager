__author__ = 'ran'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import validate_dsl as validate
from testenv import deploy_application as deploy


class TestValidateDSL(TestCase):

    def test_ok_dsl(self):
        dsl_path = resource("dsl/dependencies-order-with-two-nodes.yaml")
        deployment, _ = deploy(dsl_path)
        validate(deployment.blueprintId)

    def test_invalid_dsl(self):
        # note: this actually tests the validation part of the "deploy" command
        dsl_path = resource("dsl/invalid-dsl.yaml")

        with self.assertRaises(Exception) as cm:
            deploy(dsl_path)
            self.assertTrue('invalid blueprint' in
                            cm.exception.message.lower(), cm.exception.message)

from manager_rest import dsl_functions

from manager_rest.manager_exceptions import FunctionsEvaluationError
from manager_rest.storage import models
from manager_rest.test.base_test import BaseServerTestCase


class TestIntrinsicFunctions(BaseServerTestCase):
    def setUp(self):
        super().setUp()
        self.bp = models.Blueprint(
            id='abc',
            creator=self.user,
            tenant=self.tenant,
        )

    def test_get_sys_successful(self):
        models.Deployment(
            id='dep1',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )

        storage = dsl_functions.FunctionEvaluationStorage('dep1', self.sm)
        assert storage.get_sys('deployment', 'id') == 'dep1'
        assert storage.get_sys('deployment', 'blueprint') == self.bp.id
        assert storage.get_sys('deployment', 'owner') == self.user.username
        assert storage.get_sys('tenant', 'name') == self.tenant.name

    def test_get_sys_unknown(self):
        models.Deployment(
            id='dep2',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )

        storage = dsl_functions.FunctionEvaluationStorage('dep2', self.sm)
        with self.assertRaisesRegex(FunctionsEvaluationError, 'not-known$'):
            storage.get_sys('not', 'known')

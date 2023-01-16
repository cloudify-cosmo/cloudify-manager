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

    def test_get_consumers(self):
        infra = models.Deployment(
            id='infra',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        models.Deployment(
            id='app1',
            display_name='My App',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        models.Deployment(
            id='app2',
            display_name='Another app?',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
        )
        models.DeploymentLabel(
            deployment=infra,
            key='csys-consumer-id',
            value='app1',
            creator=self.user
        )
        models.DeploymentLabel(
            deployment=infra,
            key='csys-consumer-id',
            value='app2',
            creator=self.user
        )
        assert len(self.sm.get(models.Deployment, 'infra').labels) == 2
        storage = dsl_functions.FunctionEvaluationStorage('infra', self.sm)
        assert set(storage.get_consumers('ids')) == {'app1', 'app2'}
        assert set(storage.get_consumers('names')) == \
               {'My App', 'Another app?'}
        assert storage.get_consumers('count') == 2

    def test_get_environment_capability(self):
        models.Deployment(
            id='env',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
            capabilities={'cap1': {'value': {'a': 'b'}}},
        )
        models.Deployment(
            id='srv',
            blueprint=self.bp,
            creator=self.user,
            tenant=self.tenant,
            labels=[
                models.DeploymentLabel(
                    key='csys-obj-parent',
                    value='env',
                    creator=self.user,
                ),
            ],
        )
        env_storage = dsl_functions.FunctionEvaluationStorage('env', self.sm)
        with self.assertRaisesRegex(
            FunctionsEvaluationError,
            'csys-obj-parent'
        ):
            env_storage.get_environment_capability(['cap1'])

        srv_storage = dsl_functions.FunctionEvaluationStorage('srv', self.sm)
        with self.assertRaisesRegex(
            FunctionsEvaluationError,
            'not declared'
        ):
            srv_storage.get_environment_capability(['cap2'])

        srv_storage = dsl_functions.FunctionEvaluationStorage('srv', self.sm)
        with self.assertRaisesRegex(
            FunctionsEvaluationError,
            'nonexistent'
        ):
            srv_storage.get_environment_capability(['cap1', 'nonexistent'])

        assert 'b' == srv_storage.get_environment_capability(['cap1', 'a'])

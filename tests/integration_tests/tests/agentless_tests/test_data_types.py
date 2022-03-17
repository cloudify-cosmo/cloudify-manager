import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
class TestMiscellaneousIdInputs(AgentlessTestCase):
    def setUp(self):
        self.client.tenants.create('other_tenant')
        self.client.tenants.add_user('admin', 'other_tenant', 'manager')
        self.other_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='other_tenant'
        )

        self.client.blueprints.upload(
            utils.get_resource('dsl/blueprint_with_two_capabilities.yaml'),
            'bp-basic')
        utils.wait_for_blueprint_upload('bp-basic', self.client)
        self.client.blueprints.set_visibility('bp-basic', 'global')
        self.client.blueprints.update('bp-basic',
                                      {'labels': [{'alpha': 'bravo'}]})
        self.client.blueprints.upload(
            utils.get_resource('dsl/blueprint_with_misc_id_inputs.yaml'),
            'bp')
        utils.wait_for_blueprint_upload('bp', self.client)
        self.client.deployments_filters.create(
            'test-filter',
            [{'key': 'qwe',
              'values': ['rty'],
              'operator': 'any_of',
              'type': 'label'}])
        self.client.blueprints_filters.create(
            'test-filter',
            [{'key': 'alpha',
              'values': ['bravo'],
              'operator': 'any_of',
              'type': 'label'}])

    def setup_valid_deployments(self):
        self.client.deployments.create('bp-basic', 'deploymentA',
                                       labels=[{'qwe': 'rty'},
                                               {'foo': 'bar'}])
        self.client.deployments.create('bp-basic', 'deploymentB',
                                       labels=[{'foo': 'bar'},
                                               {'lorem': 'ipsum'}])
        self.other_client.deployments.create('bp-basic', 'deploymentC')
        self.other_client.deployments.set_visibility('deploymentC', 'global')
        self.client.deployments.create('bp-basic', 'deploymentD')

    def setup_valid_secrets(self):
        self.client.secrets.create('secret_one', 'value1')
        self.client.secrets.create('secret_two', 'value2')
        self.client.secrets.create('secret_three', 'value3')

    def test_successful(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()
        self.client.deployments.create(
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability2_value',
                    'a_secret_key': 'secret_one'})
        install_execution = self.client.executions.create('d1', 'install')
        self.wait_for_execution_to_end(install_execution)

        for node in self.client.nodes.list(
                deployment_id='d1', _include=['id', 'properties']):
            if node['id'] == 'node_a':
                assert node['properties']['deployment_id'] == 'deploymentA'
            elif node['id'] == 'node_b':
                assert node['properties']['deployment_id'] == 'deploymentB'
            elif node['id'] == 'node_c':
                assert node['properties']['deployment_id'] == 'deploymentC'
            elif node['id'] == 'node_d':
                assert node['properties']['deployment_id'] == 'deploymentD'
            else:
                assert False

    def test_deployment_id_errors(self):
        self.client.deployments.create('bp-basic', 'deploymentA',
                                       labels=[{'qwe': 'rty'},
                                               {'foo': 'bar'}])
        self.client.deployments.create('bp-basic', 'deploymentB',
                                       labels=[{'foo': 'bar'},
                                               {'lorem': 'ipsum'}])
        self.other_client.deployments.create('bp-basic', 'deploymentC')
        self.other_client.deployments.set_visibility('deploymentC', 'global')
        self.client.deployments.create('bp-basic', 'deploymentD')

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+filter_id',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentD',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+labels',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentA',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+tenants',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentB',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})

        self.client.deployments.create('bp-basic', 'not_a_deploymentD')
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+name_pattern',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'not_a_deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})

    def test_blueprint_id_errors(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_blueprint_id.+labels',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b_blueprint_id.+filter_id',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})

    def test_secret_key_errors(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_secret_key',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability2_value',
                    'a_secret_key': 'secret_two'})
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_secret_key',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability2_value',
                    'a_secret_key': 'secret_five'})

    def test_capability_value_errors(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_capability_value',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'non existent value',
                    'b_capability_value': 'capability1_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b_capability_value',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability1_value',
                    'c_capability_value': 'capability1_value',
                    'a_secret_key': 'secret_one'})
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+c_capability_value',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD',
                    'a_blueprint_id': 'bp-basic',
                    'b_blueprint_id': 'bp-basic',
                    'a_capability_value': 'capability1_value',
                    'b_capability_value': 'capability2_value',
                    'c_capability_value': 'capability3_value',
                    'a_secret_key': 'secret_one'})


@pytest.mark.usefixtures('cloudmock_plugin')
class TestMiscellaneousIdParams(AgentlessTestCase):
    def setUp(self):
        self.client.tenants.create('other_tenant')
        self.client.tenants.add_user('admin', 'other_tenant', 'manager')
        self.other_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='other_tenant'
        )

        self.client.blueprints.upload(
            utils.get_resource('dsl/blueprint_with_two_capabilities.yaml'),
            'bp-basic')
        utils.wait_for_blueprint_upload('bp-basic', self.client)
        self.client.blueprints.update('bp-basic',
                                      {'labels': [{'alpha': 'bravo'}]})
        self.client.blueprints.set_visibility('bp-basic', 'global')
        self.client.blueprints.upload(
            utils.get_resource(
                'dsl/blueprint_with_misc_id_parameters.yaml'),
            'bp')
        utils.wait_for_blueprint_upload('bp', self.client)
        self.client.deployments_filters.create(
            'test-filter',
            [{'key': 'qwe',
              'values': ['rty'],
              'operator': 'any_of',
              'type': 'label'}])

    def test_successful(self):
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.client.deployments.create('bp', 'd1')

        test_execution = self.client.executions.create(
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )
        self.wait_for_execution_to_end(test_execution)

    def test_deployment_id_error(self):
        self.client.deployments.create('bp', 'd1')
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_deployment_id',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 3.14,
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'foo': 'bar'}, {'sit': 'amet'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+filter_id',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.other_client.deployments.create(
            'bp-basic',
            'deploymentAA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}])
        self.other_client.deployments.set_visibility('deploymentAA', 'global')
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+labels',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentAA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.client.deployments.create(
            'bp-basic',
            'deploymentAAA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.client.deployments.set_visibility('deploymentAAA', 'global')
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+tenants',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentAAA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.other_client.deployments.create(
            'bp-basic',
            'deploymentABC',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentABC', 'global')
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+name_pattern',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentABC',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

    def test_blueprint_id_errors(self):
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.client.deployments.create('bp', 'd1')

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_blueprint_id',
            self.client.executions.create,
            'd1', 'test_parameters',
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': -99,
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b_blueprint_id',
            self.client.executions.create,
            'd1', 'test_parameters',
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'non-existent',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_blueprint_id.+labels',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': 'bp',
                        'b_blueprint_id': 'bp-basic',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability1_value'},
        )

    def test_capability_value_errors(self):
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.client.deployments.create('bp', 'd1')

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_capability_value',
            self.client.executions.create,
            'd1', 'test_parameters',
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability1_value',
                        'b_capability_value': 'capability1_value'},
        )

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b_capability_value',
            self.client.executions.create,
            'd1', 'test_parameters',
            parameters={'a_deployment_id': 'deploymentA',
                        'a_blueprint_id': 'bp-basic',
                        'b_blueprint_id': 'bp',
                        'a_capability_value': 'capability2_value',
                        'b_capability_value': 'capability3_value'},
        )

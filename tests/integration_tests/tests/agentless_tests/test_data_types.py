import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils

pytestmark = pytest.mark.group_deployments


class DataBasedTypes:
    def upload_blueprint(self,
                         client=None,
                         blueprint_id='bp',
                         blueprint_file_name='basic.yaml',
                         labels=None,
                         visibility=None,
                         ):
        client = client or self.client
        client.blueprints.upload(
            utils.get_resource(f'dsl/{blueprint_file_name}'),
            blueprint_id
        )
        utils.wait_for_blueprint_upload(blueprint_id, client)
        if visibility:
            client.blueprints.set_visibility(blueprint_id, visibility)
        if labels:
            self.client.blueprints.update(blueprint_id,
                                          {'labels': labels})

    def setup_valid_secrets(self):
        self.client.secrets.create('secret_one', 'value1')
        self.client.secrets.create('secret_two', 'value2')
        self.client.secrets.create('secret_three', 'value3')

    @staticmethod
    def get_inputs(**kwargs):
        inputs = {'a_deployment_id': 'deploymentA',
                  'b_deployment_id': 'deploymentB',
                  'c_deployment_id': 'deploymentC',
                  'd_deployment_id': 'deploymentD',
                  'a_blueprint_id': 'bp-basic',
                  'b_blueprint_id': 'bp-basic',
                  'a_capability_value': 'capability1_value',
                  'b_capability_value': 'capability2_value',
                  'c_capability_value': 'capability2_value',
                  'a_secret_key': 'secret_one'}
        inputs.update(kwargs)
        return inputs

    @staticmethod
    def get_params(**kwargs):
        params = {'a_deployment_id': 'deploymentA',
                  'a_blueprint_id': 'bp-basic',
                  'b_blueprint_id': 'bp',
                  'a_capability_value': 'capability2_value',
                  'b_capability_value': 'capability1_value',
                  'a_secret_key': 'secret_one'}
        params.update(kwargs)
        return params


@pytest.mark.usefixtures('cloudmock_plugin')
class TestDataBasedTypeInputs(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        self.client.tenants.create('other_tenant')
        self.client.tenants.add_user('admin', 'other_tenant', 'manager')
        self.other_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='other_tenant'
        )

        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_capabilities.yaml',
            visibility='global',
            labels=[{'alpha': 'bravo'}],
        )
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_data_based_inputs.yaml',
        )
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

    def test_successful(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()
        self.client.deployments.create('bp', 'd1', inputs=self.get_inputs())
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
        self.client.deployments.create(
            'bp-basic', 'deploymentA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}]
        )
        self.client.deployments.create(
            'bp-basic', 'deploymentB',
            labels=[{'foo': 'bar'}, {'lorem': 'ipsum'}]
        )
        self.other_client.deployments.create('bp-basic', 'deploymentC')
        self.other_client.deployments.set_visibility('deploymentC', 'global')
        self.client.deployments.create('bp-basic', 'deploymentD')
        self.client.deployments.create('bp-basic', 'not_a_deploymentD')

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+filter_id',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(a_deployment_id='deploymentD'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+labels',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(b_deployment_id='deploymentA'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+tenants',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(c_deployment_id='deploymentB'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+name_pattern',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(d_deployment_id='not_a_deploymentD'),
        )

    def test_blueprint_id_errors(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_blueprint_id.+labels',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(a_blueprint_id='bp'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b_blueprint_id.+filter_id',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(b_blueprint_id='bp'),
        )

    def test_secret_key_errors(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_secret_key',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(a_secret_key='secret_two'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_secret_key',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(a_secret_key='secret_five'),
        )

    def test_capability_value_errors(self):
        self.setup_valid_deployments()
        self.setup_valid_secrets()

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a_capability_value',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(a_capability_value='non existent value'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b_capability_value',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(b_capability_value='capability1_value'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+c_capability_value',
            self.client.deployments.create,
            'bp', 'd1',
            inputs=self.get_inputs(c_capability_value='capability3_value'),
        )


@pytest.mark.usefixtures('cloudmock_plugin')
class TestDataBasedTypeParams(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        self.client.tenants.create('other_tenant')
        self.client.tenants.add_user('admin', 'other_tenant', 'manager')
        self.other_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='other_tenant'
        )
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_capabilities.yaml',
            labels=[{'alpha': 'bravo'}],
            visibility='global',
        )
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_data_based_parameters.yaml',
        )
        self.client.deployments_filters.create(
            'test-filter',
            [{'key': 'qwe',
              'values': ['rty'],
              'operator': 'any_of',
              'type': 'label'}])
        self.client.secrets.create('secret_one', 'value1')
        self.client.secrets.create('secret_two', 'value2')
        self.client.secrets.create('secret_three', 'value3')

    def test_successful(self):
        self.other_client.deployments.create(
            'bp-basic', 'deploymentA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}]
        )
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.client.deployments.create('bp', 'd1')

        test_execution = self.client.executions.create(
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(),
        )
        self.wait_for_execution_to_end(test_execution)

    def test_deployment_id_error(self):
        self.client.deployments.create('bp', 'd1')
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'foo': 'bar'}, {'sit': 'amet'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentAA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}])
        self.other_client.deployments.set_visibility('deploymentAA', 'global')
        self.client.deployments.create(
            'bp-basic',
            'deploymentAAA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.client.deployments.set_visibility('deploymentAAA', 'global')
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentABC',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentABC', 'global')

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_deployment_id',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(a_deployment_id=3.14),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+filter_id',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+labels',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(a_deployment_id='deploymentAA'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+tenants',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(a_deployment_id='deploymentAAA'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+name_pattern',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(a_deployment_id='deploymentABC'),
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
            parameters=self.get_params(a_blueprint_id=-99),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b_blueprint_id',
            self.client.executions.create,
            'd1', 'test_parameters',
            parameters=self.get_params(b_blueprint_id='non-existent'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_blueprint_id.+labels',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters=self.get_params(a_blueprint_id='bp'),
        )

    def test_secret_key_errors(self):
        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.client.deployments.create('bp', 'd1')

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_secret_key',
            self.client.executions.create,
            'd1', 'test_parameters',
            allow_custom_parameters=True,
            parameters=self.get_params(a_secret_key='secret_two'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a_secret_key',
            self.client.executions.create,
            'd1', 'test_parameters',
            allow_custom_parameters=True,
            parameters=self.get_params(a_secret_key='secret_five'),
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
            parameters=self.get_params(a_capability_value='capability1_value'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b_capability_value',
            self.client.executions.create,
            'd1', 'test_parameters',
            parameters=self.get_params(b_capability_value='capability3_value'),
        )


class TestNodeTemplateType(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_nodes.yaml',
        )
        self.client.deployments.create('bp-basic', 'dep-basic')
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_node_template_data_type.yaml'
        )
        self.setup_valid_secrets()

    @staticmethod
    def get_inputs(**kwargs):
        inputs = {'a': 'node1',
                  'b': 'node2',
                  'c': 'node2'}
        inputs.update(kwargs)
        return inputs

    @staticmethod
    def get_params(**kwargs):
        params = {'a': 'node1',
                  'b': 'node2',
                  'c': 'node2'}
        params.update(kwargs)
        return params

    def test_successful(self):
        self.client.deployments.create(
            'bp', 'dep', inputs=self.get_inputs())
        install_execution = self.client.executions.create('dep', 'install')
        self.wait_for_execution_to_end(install_execution)
        test_execution = self.client.executions.create(
            'dep', 'test_parameters', parameters=self.get_params())
        self.wait_for_execution_to_end(test_execution)

    def test_input_errors(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a.+name_pattern',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(a='node2'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b.+valid_values',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(b='node1'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+input.+c.+does not match',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(c='node-that-does-not-exist'),
        )

    def test_param_errors(self):
        self.client.deployments.create(
            'bp', 'dep', inputs=self.get_inputs())

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a.+name_pattern',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(a='node2'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b.+valid_values',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(b='node1'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+c.+does not match',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(c='node-that-does-not-exist'),
        )

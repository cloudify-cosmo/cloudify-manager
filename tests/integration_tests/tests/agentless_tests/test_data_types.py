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
        super().setUp()
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
        super().setUp()
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


class TestNodeIdType(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        super().setUp()
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_nodes.yaml',
        )
        self.client.deployments.create('bp-basic', 'dep-basic')
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_node_id_data_type.yaml'
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


class TestNodeTypeType(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        super().setUp()
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_nodes.yaml',
        )
        self.client.deployments.create('bp-basic', 'dep-basic')
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_node_type_data_type.yaml'
        )
        self.setup_valid_secrets()

    @staticmethod
    def get_inputs(**kwargs):
        inputs = {'a': 'type1',
                  'b': 'type2',
                  'c': 'type2'}
        inputs.update(kwargs)
        return inputs

    @staticmethod
    def get_params(**kwargs):
        params = {'a': 'type1',
                  'b': 'type2',
                  'c': 'type2'}
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
            inputs=self.get_inputs(a='type2'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b.+valid_values',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(b='type1'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+input.+c.+does not match',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(c='type-that-does-not-exist'),
        )

    def test_param_errors(self):
        self.client.deployments.create(
            'bp', 'dep', inputs=self.get_inputs())

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a.+name_pattern',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(a='type2'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b.+valid_values',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(b='type1'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+c.+does not match',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(c='type-that-does-not-exist'),
        )


class TestNodeInstanceType(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        super().setUp()
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_nodes.yaml',
        )
        self.client.deployments.create('bp-basic', 'dep-basic')
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_node_instance_data_type.yaml'
        )
        self.setup_valid_secrets()

    @staticmethod
    def get_inputs(**kwargs):
        node_instance_ids = kwargs.pop('ids', {})
        inputs = {'a': node_instance_ids.get('node1'),
                  'b': node_instance_ids.get('node2')}
        inputs.update(kwargs)
        return inputs

    @staticmethod
    def get_params(**kwargs):
        node_instance_ids = kwargs.pop('ids', {})
        params = {'a': node_instance_ids.get('node1'),
                  'b': node_instance_ids.get('node2')}
        params.update(kwargs)
        return params

    def test_successful(self):
        node_instances = self.client.node_instances.list(
            deployment_id='dep-basic')
        node_instance_ids = {n.node_id: n.id for n in node_instances}
        self.client.deployments.create(
            'bp', 'dep',
            inputs=self.get_inputs(ids=node_instance_ids))
        install_execution = self.client.executions.create('dep', 'install')
        self.wait_for_execution_to_end(install_execution)
        test_execution = self.client.executions.create(
            'dep', 'test_parameters',
            parameters=self.get_params(ids=node_instance_ids))
        self.wait_for_execution_to_end(test_execution)

    def test_input_errors(self):
        node_instances = self.client.node_instances.list(
            deployment_id='dep-basic')
        node_instance_ids = {n.node_id: n.id for n in node_instances}
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+a.+name_pattern',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(ids=node_instance_ids,
                                   a=node_instance_ids['node2']),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+input.+b.+does not match',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(ids=node_instance_ids,
                                   b='node-that-does-not-exist'),
        )

    def test_param_errors(self):
        node_instances = self.client.node_instances.list(
            deployment_id='dep-basic')
        node_instance_ids = {n.node_id: n.id for n in node_instances}
        self.client.deployments.create(
            'bp', 'dep',
            inputs=self.get_inputs(ids=node_instance_ids))

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a.+name_pattern',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(ids=node_instance_ids,
                                       a=node_instance_ids['node2']),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+b.+does not match',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(ids=node_instance_ids,
                                       b='node-that-does-not-exist'),
        )


class TestScalingGroupType(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        super().setUp()
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_scaling_groups.yaml',
        )
        self.client.deployments.create('bp-basic', 'dep-basic')
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_scaling_group_data_type.yaml'
        )
        self.setup_valid_secrets()

    @staticmethod
    def get_inputs(**kwargs):
        inputs = {'a': 'first_node',
                  'b': 'other_nodes'}
        inputs.update(kwargs)
        return inputs

    @staticmethod
    def get_params(**kwargs):
        params = {'a': 'first_node',
                  'b': 'other_nodes'}
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
            inputs=self.get_inputs(a='second_node'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+b.+does not match',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(b='nonexistent_nodes'),
        )

    def test_param_errors(self):
        self.client.deployments.create(
            'bp', 'dep', inputs=self.get_inputs())

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+a.+name_pattern',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(a='second_noe'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+c.+does not match',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(b='scaling-group-that-does-not-exist'),
        )


class TestListTypes(AgentlessTestCase, DataBasedTypes):
    def test_inputs(self):
        # Preparations
        self.upload_blueprint(
            blueprint_id='b1',
            blueprint_file_name='blueprint_with_list_types.yaml',
        )

        # Tests
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+False.+truths_list violates constraint valid_values",
            self.client.deployments.create,
            'b1', 'd1',
            inputs={
                'truths_list': [True, False, True, False],
                'floats_list': [3.1416],
                'ints_list': [0, 1, 2, 3],
            }
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+type validation failed in 'floats_list'",
            self.client.deployments.create,
            'b1', 'd1',
            inputs={
                'truths_list': [True, True],
                'floats_list': [3.1416, True],
                'ints_list': [0, 1, 2, 3],
            }
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+type validation failed in 'ints_list'",
            self.client.deployments.create,
            'b1', 'd1',
            inputs={
                'truths_list': [True, True],
                'floats_list': [3.1416, 1.4142],
                'ints_list': [0, 'foo'],
            }
        )

        # Preparations cont.
        self.client.deployments.create(
            'b1', 'd1',
            inputs={
                'truths_list': [True, True],
                'floats_list': [3.1416, 1.4142],
                'ints_list': [-9, 23],
            }
        )
        self.upload_blueprint(
            blueprint_id='b2',
            blueprint_file_name='blueprint_with_list_types.yaml',
        )
        self.client.deployments.create(
            'b2', 'd2',
            inputs={
                'truths_list': [True],
                'floats_list': [3.1416],
                'ints_list': [],
            }
        )

        # Tests
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_list_data_based_types.yaml',
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+'blueprint-which-does-not-exist'.+is not a valid value",
            self.client.deployments.create,
            'bp', 'dep1',
            inputs={
                'blueprints_list': ['b1', 'blueprint-which-does-not-exist'],
                'deployments_list': [],
                'nodes_list': [],
                'node_instances_list': [],
            }
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+d2.+deployments_list violates constraint valid_values",
            self.client.deployments.create,
            'bp', 'dep1',
            inputs={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1', 'd2'],
                'nodes_list': [],
                'node_instances_list': [],
            }
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+input 'nodes_list' does not match",
            self.client.deployments.create,
            'bp', 'dep1',
            inputs={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1'],
                'nodes_list': ['non-existent-node'],
                'node_instances_list': [],
            }
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+'3.1416'.+violates at least one of the constraints",
            self.client.deployments.create,
            'bp', 'dep1',
            inputs={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1'],
                'nodes_list': [],
                'node_instances_list': [3.1416],
            }
        )

    def test_params(self):
        # Preparations
        self.upload_blueprint(
            blueprint_id='b1',
            blueprint_file_name='blueprint_with_list_types.yaml',
        )
        self.client.deployments.create(
            'b1', 'd1',
            inputs={
                'truths_list': [True, True],
                'floats_list': [3.1416, 1.4142],
                'ints_list': [-9, 23],
            }
        )
        self.upload_blueprint(
            blueprint_id='b2',
            blueprint_file_name='blueprint_with_list_types.yaml',
        )
        self.client.deployments.create(
            'b2', 'd2',
            inputs={
                'truths_list': [True],
                'floats_list': [3.1416],
                'ints_list': [],
            }
        )
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_list_data_based_types.yaml',
        )
        self.client.deployments.create(
            'bp', 'dep1',
            inputs={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1'],
                'nodes_list': [],
                'node_instances_list': [],
            }
        )

        # Tests
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+Value b2.+violates constraint valid_values",
            self.client.executions.create,
            'dep1', 'test_parameters',
            parameters={
                'blueprints_list': ['b1', 'b2'],
                'deployments_list': ['d1'],
                'nodes_list': [],
                'node_instances_list': [],
            },
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+Value 'False'.+not a valid value",
            self.client.executions.create,
            'dep1', 'test_parameters',
            parameters={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1', False],
                'nodes_list': [],
                'node_instances_list': [],
            },
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+Value 'node1' of 'nodes_list' is not a valid value",
            self.client.executions.create,
            'dep1', 'test_parameters',
            parameters={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1'],
                'nodes_list': ['node1', 'node2'],
                'node_instances_list': [],
            },
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r"^400:.+Value 'root_node'.+does not match",
            self.client.executions.create,
            'dep1', 'test_parameters',
            parameters={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1'],
                'nodes_list': ['root_node'],
                'node_instances_list': ['root_node'],
            },
        )
        d2_node_instances = self.client.node_instances.list(deployment_id='d2')
        test_execution = self.client.executions.create(
            'dep1', 'test_parameters',
            parameters={
                'blueprints_list': ['b1'],
                'deployments_list': ['d1'],
                'nodes_list': ['root_node'],
                'node_instances_list': [ni.id for ni in d2_node_instances],
            },
        )
        self.wait_for_execution_to_end(test_execution)


class TestOperationNameType(AgentlessTestCase, DataBasedTypes):
    def setUp(self):
        super().setUp()
        self.upload_blueprint(
            blueprint_id='bp-basic',
            blueprint_file_name='blueprint_with_two_nodes.yaml',
        )
        self.client.deployments.create('bp-basic', 'dep-basic')
        self.upload_blueprint(
            blueprint_id='bp',
            blueprint_file_name='blueprint_with_operation_name_data_type.yaml'
        )

    @staticmethod
    def get_inputs(**kwargs):
        inputs = {'input_a': 'cloudify.interfaces.lifecycle.configure',
                  'input_b': 'update_postapply'}
        inputs.update(kwargs)
        return inputs

    @staticmethod
    def get_params(**kwargs):
        params = {'param_a': 'cloudify.interfaces.lifecycle.configure',
                  'param_b': 'update_postapply'}
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
            r'^400:.+ConstraintException:.+input_a.+name_pattern',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(input_a='check_drift'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+input_b.+does not match',
            self.client.deployments.create,
            'bp', 'dep',
            inputs=self.get_inputs(input_b='nonexistent_operation_name'),
        )

    def test_param_errors(self):
        self.client.deployments.create(
            'bp', 'dep', inputs=self.get_inputs())

        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+param_a.+name_pattern',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(param_a='second_noe'),
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+param_b.+does not match',
            self.client.executions.create,
            'dep', 'test_parameters',
            parameters=self.get_params(param_b='op-name-that-does-not-exist'),
        )

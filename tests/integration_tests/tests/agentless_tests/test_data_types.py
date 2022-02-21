import pytest

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests import utils

pytestmark = pytest.mark.group_deployments


@pytest.mark.usefixtures('cloudmock_plugin')
class TestDeploymentIdInputs(AgentlessTestCase):
    def setUp(self):
        self.client.tenants.create('other_tenant')
        self.client.tenants.add_user('admin', 'other_tenant', 'manager')
        self.other_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='other_tenant'
        )

        self.client.blueprints.upload(
            utils.get_resource('dsl/basic.yaml'),
            'bp-basic')
        utils.wait_for_blueprint_upload('bp-basic', self.client)
        self.client.blueprints.set_visibility('bp-basic', 'global')
        self.client.blueprints.upload(
            utils.get_resource('dsl/blueprint_with_deployment_id_inputs.yaml'),
            'bp')
        utils.wait_for_blueprint_upload('bp', self.client)
        self.client.deployments_filters.create(
            'test-filter',
            [{'key': 'qwe',
              'values': ['rty'],
              'operator': 'any_of',
              'type': 'label'}])

    def test_successful(self):
        self.client.deployments.create('bp-basic', 'deploymentA',
                                       labels=[{'qwe': 'rty'},
                                               {'foo': 'bar'}])
        self.client.deployments.create('bp-basic', 'deploymentB',
                                       labels=[{'foo': 'bar'},
                                               {'lorem': 'ipsum'}])
        self.other_client.deployments.create('bp-basic', 'deploymentC')
        self.other_client.deployments.set_visibility('deploymentC', 'global')
        self.client.deployments.create('bp-basic', 'deploymentD')

        self.client.deployments.create(
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD'})
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

    def test_filter_id_constraint_error(self):
        self.client.deployments.create('bp-basic', 'deploymentA',
                                       labels=[{'qwe': 'rty'},
                                               {'foo': 'bar'}])
        self.client.deployments.create('bp-basic', 'deploymentB',
                                       labels=[{'foo': 'bar'},
                                               {'lorem': 'ipsum'}])
        self.other_client.deployments.create('bp-basic', 'deploymentC')
        self.other_client.deployments.set_visibility('deploymentC', 'global')
        self.client.deployments.create('bp-basic', 'deploymentD')

        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+filter_id',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentD',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD'})

        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+labels',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentA',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'deploymentD'})

        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+tenants',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentB',
                    'd_deployment_id': 'deploymentD'})

        self.client.deployments.create('bp-basic', 'not_a_deploymentD')
        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+ConstraintException:.+name_pattern',
            self.client.deployments.create,
            'bp', 'd1',
            inputs={'a_deployment_id': 'deploymentA',
                    'b_deployment_id': 'deploymentB',
                    'c_deployment_id': 'deploymentC',
                    'd_deployment_id': 'not_a_deploymentD'})


@pytest.mark.usefixtures('cloudmock_plugin')
class TestDeploymentIdParameters(AgentlessTestCase):
    def setUp(self):
        self.client.tenants.create('other_tenant')
        self.client.tenants.add_user('admin', 'other_tenant', 'manager')
        self.other_client = self.create_rest_client(
            username='admin',
            password='admin',
            tenant='other_tenant'
        )

        self.client.blueprints.upload(
            utils.get_resource('dsl/basic.yaml'),
            'bp-basic')
        utils.wait_for_blueprint_upload('bp-basic', self.client)
        self.client.blueprints.set_visibility('bp-basic', 'global')
        self.client.blueprints.upload(
            utils.get_resource(
                'dsl/blueprint_with_deployment_id_parameters.yaml'),
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
            parameters={'a_deployment_id': 'deploymentA'},
        )
        self.wait_for_execution_to_end(test_execution)

    def test_not_deployment_id_error(self):
        self.client.deployments.create('bp', 'd1')
        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+filter_id',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 3.14},
        )

        self.other_client.deployments.create(
            'bp-basic',
            'deploymentA',
            labels=[{'foo': 'bar'}, {'sit': 'amet'}])
        self.other_client.deployments.set_visibility('deploymentA', 'global')
        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+filter_id',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentA'},
        )

        self.other_client.deployments.create(
            'bp-basic',
            'deploymentAA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}])
        self.other_client.deployments.set_visibility('deploymentAA', 'global')
        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+labels',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentAA'},
        )

        self.client.deployments.create(
            'bp-basic',
            'deploymentAAA',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.client.deployments.set_visibility('deploymentAAA', 'global')
        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+tenants',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentAAA'},
        )

        self.other_client.deployments.create(
            'bp-basic',
            'deploymentABC',
            labels=[{'qwe': 'rty'}, {'foo': 'bar'}, {'lorem': 'ipsum'}])
        self.other_client.deployments.set_visibility('deploymentABC', 'global')
        self.assertRaisesRegexp(
            CloudifyClientError,
            r'^400:.+Parameter.+constraints:.+name_pattern',
            self.client.executions.create,
            'd1', 'test_parameters', allow_custom_parameters=True,
            parameters={'a_deployment_id': 'deploymentABC'},
        )

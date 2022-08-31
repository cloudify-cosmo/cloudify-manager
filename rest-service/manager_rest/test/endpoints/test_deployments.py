#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import errno
import mock
import os
import uuid
from datetime import datetime
from typing import Optional, Dict

from cloudify.models_states import (VisibilityState,
                                    ExecutionState,
                                    DeploymentState)
from dsl_parser import exceptions as dsl_exceptions

from manager_rest.test import base_test
from manager_rest import manager_exceptions
from manager_rest.storage import models
from manager_rest.constants import (DEFAULT_TENANT_NAME,
                                    FILE_SERVER_DEPLOYMENTS_FOLDER)
from manager_rest.rest.filters_utils import FilterRule

from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    MissingRequiredDeploymentInputError,
)


TEST_PACKAGE_NAME = 'cloudify-script-plugin'
TEST_PACKAGE_VERSION = '1.2'


class TestCheckDeploymentDelete(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        self._bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )

    def _deployment(self, **kwargs):
        params = {
            'blueprint': self._bp,
            'creator': self.user,
            'tenant': self.tenant
        }
        params.update(kwargs)
        return models.Deployment(**params)

    def test_allowed_delete(self):
        dep = self._deployment(id='dep1')
        self.rm.check_deployment_delete(dep)  # doesn't throw

    def test_existing_execution_status(self):
        dep = self._deployment(id='dep1')
        for exc_status in [
            ExecutionState.STARTED,
            ExecutionState.PENDING,
            ExecutionState.QUEUED,
        ]:
            with self.subTest():
                exc_id = str(uuid.uuid4())
                models.Execution(
                    id=exc_id,
                    workflow_id='',
                    deployment=dep,
                    status=exc_status,
                    tenant=self.tenant,
                    creator=self.user,
                )
                with self.assertRaisesRegex(
                        manager_exceptions.DependentExistsError, exc_id):
                    self.rm.check_deployment_delete(dep)

    def test_finished_execution(self):
        dep = self._deployment(id='dep1')
        for exc_status in [
            ExecutionState.TERMINATED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        ]:
            with self.subTest():
                models.Execution(
                    id='exc1',
                    workflow_id='',
                    deployment=dep,
                    status=exc_status,
                    tenant=self.tenant,
                    creator=self.user,
                )
                self.rm.check_deployment_delete(dep)  # doesn't throw

    def test_dependent_exist(self):
        # dep2 is used inside dep1
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            dependency_creator='',
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm.check_deployment_delete(dep1)  # doesnt throw
        with self.assertRaises(manager_exceptions.DependentExistsError):
            # you can't just delete a component, dep1 uses it; it must be
            # deleted by deleting dep1 as well
            self.rm.check_deployment_delete(dep2)

    def test_allowed_component_delete(self):
        # dep2 is a component used inside dep1
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )
        models.Execution(
            id='exc1',
            workflow_id='uninstall',
            status=ExecutionState.STARTED,
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm.check_deployment_delete(dep2)  # doesnt throw

    def test_parent_child(self):
        # dep2 is dep1's parent
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.DeploymentLabelsDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm.check_deployment_delete(dep1)  # doesnt throw
        with self.assertRaises(manager_exceptions.DependentExistsError):
            # you can't delete parents whose children still exist
            self.rm.check_deployment_delete(dep2)

    def test_parent_component(self):
        # dep2 is dep1's parent AND dep1 is a component used inside of dep2
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.DeploymentLabelsDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        models.InterDeploymentDependencies(
            source_deployment=dep2,
            target_deployment=dep1,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )

        with self.assertRaises(manager_exceptions.DependentExistsError):
            self.rm.check_deployment_delete(dep1)
        with self.assertRaises(manager_exceptions.DependentExistsError):
            self.rm.check_deployment_delete(dep2)

        models.Execution(
            id='exc1',
            workflow_id='uninstall',
            status=ExecutionState.STARTED,
            deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )

        self.rm.check_deployment_delete(dep1)  # doesnt throw
        with self.assertRaises(manager_exceptions.DependentExistsError):
            # you can't delete parents whose children still exist
            self.rm.check_deployment_delete(dep2)

    def test_started_instance(self):
        # dep2 is dep1's parent
        dep1 = self._deployment(id='dep1')
        node = models.Node(
            deployment=dep1,
            type='',
            number_of_instances=1,
            planned_number_of_instances=1,
            deploy_number_of_instances=1,
            min_number_of_instances=1,
            max_number_of_instances=1,
            creator=self.user,
            tenant=self.tenant,
        )
        node_instance = models.NodeInstance(
            id='ni_1',
            state='started',
            node=node,
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaisesRegex(
                manager_exceptions.DependentExistsError, node_instance.id):
            self.rm.check_deployment_delete(dep1)

    def test_uninitialized_instance(self):
        # dep2 is dep1's parent
        dep1 = self._deployment(id='dep1')
        node = models.Node(
            deployment=dep1,
            type='',
            number_of_instances=1,
            planned_number_of_instances=1,
            deploy_number_of_instances=1,
            min_number_of_instances=1,
            max_number_of_instances=1,
            creator=self.user,
            tenant=self.tenant,
        )
        models.NodeInstance(
            id='ni_1',
            state='uninitialized',
            node=node,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm.check_deployment_delete(dep1)  # doesnt throw

    def test_external_dependency_source(self):
        dep1 = self._deployment(id='dep1')
        models.InterDeploymentDependencies(
            target_deployment=dep1,
            dependency_creator='',
            external_source='external-source',
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaises(manager_exceptions.DependentExistsError):
            self.rm.check_deployment_delete(dep1)

    def test_external_dependency_target(self):
        dep1 = self._deployment(id='dep1')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            dependency_creator='',
            external_target='external-target',
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm.check_deployment_delete(dep1)  # doesnt throw

    def test_external_component_creator(self):
        dep1 = self._deployment(id='dep1')
        models.InterDeploymentDependencies(
            target_deployment=dep1,
            dependency_creator='component.x',
            external_source='{source_json: values}',
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm.check_deployment_delete(dep1)  # doesnt throw


class TestValidateExecutionDependencies(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        self._bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )

    def _deployment(self, **kwargs):
        params = {
            'blueprint': self._bp,
            'creator': self.user,
            'tenant': self.tenant
        }
        params.update(kwargs)
        dep = models.Deployment(**params)
        return dep

    def test_non_destructive_workflow(self):
        dep = self._deployment(id='dep1')
        exc = models.Execution(
            id='exc1',
            workflow_id='execute_operation',
            deployment=dep,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc, False)  # doesn't throw

    def test_no_dependencies(self):
        dep = self._deployment(id='dep1')
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc, False)  # doesn't throw

    def test_uninstall_parent(self):
        # dep2 is dep1's parent
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.DeploymentLabelsDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaises(manager_exceptions.DependentExistsError):
            # you can't uninstall parents whose children still exist
            self.rm._verify_dependencies_not_affected(exc, False)

    def test_uninstall_child(self):
        # dep2 is dep1's parent
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.DeploymentLabelsDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc, False)

    def test_uninstall_dependency(self):
        # dep2 is a component used inside dep1
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaises(manager_exceptions.DependentExistsError):
            self.rm._verify_dependencies_not_affected(exc, False)

    def test_uninstall_dependent(self):
        # dep2 is a component used inside dep1
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc, False)  # doesnt throw

    def test_uninstall_parent_component(self):
        # dep2 is dep1's parent AND dep1 is a component used inside of dep2
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.DeploymentLabelsDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        models.InterDeploymentDependencies(
            source_deployment=dep2,
            target_deployment=dep1,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep2,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc, False)  # doesnt throw

    def test_uninstall_capability_dependency(self):
        # dep2 is using a capability of dep1
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        models.InterDeploymentDependencies(
            source_deployment=dep2,
            target_deployment=dep1,
            dependency_creator='x.get_capability',
            creator=self.user,
            tenant=self.tenant,
        )
        # uninstall should fail when the dependent is active
        dep2.installation_status = DeploymentState.ACTIVE
        exc1 = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaises(manager_exceptions.DependentExistsError):
            self.rm._verify_dependencies_not_affected(exc1, False)

        # uninstall should succeed when the dependent is inactive
        dep2.installation_status = DeploymentState.INACTIVE
        exc2 = models.Execution(
            id='exc2',
            workflow_id='uninstall',
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc2, False)  # doesnt throw

    def test_external_dependency_source(self):
        dep1 = self._deployment(id='dep1')
        models.InterDeploymentDependencies(
            target_deployment=dep1,
            dependency_creator='',
            external_source='external-source',
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        with self.assertRaises(manager_exceptions.DependentExistsError):
            self.rm._verify_dependencies_not_affected(exc, False)

    def test_external_dependency_target(self):
        dep1 = self._deployment(id='dep1')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            dependency_creator='',
            external_target='external-target',
            creator=self.user,
            tenant=self.tenant,
        )
        exc = models.Execution(
            id='exc1',
            workflow_id='uninstall',
            deployment=dep1,
            creator=self.user,
            tenant=self.tenant,
        )
        self.rm._verify_dependencies_not_affected(exc, False)  # doesnt throw


class TestLicensedEnvironments(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        self._bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )

    def _deployment(self, **kwargs):
        params = {
            'blueprint': self._bp,
            'creator': self.user,
            'tenant': self.tenant
        }
        params.update(kwargs)
        dep = models.Deployment(**params)
        return dep

    def test_licensed_environments(self):
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        dep3 = self._deployment(id='dep3')
        dep4 = self._deployment(id='dep4')
        models.InterDeploymentDependencies(
            source_deployment=dep1,
            target_deployment=dep2,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )
        models.InterDeploymentDependencies(
            source_deployment=dep2,
            target_deployment=dep3,
            dependency_creator='component.x',
            creator=self.user,
            tenant=self.tenant,
        )
        env_list = self.client.deployments.list(_environments_only=True)
        self.assertEqual(2, len(env_list))
        self.assertEqual({dep1.id, dep4.id},
                         set(x.id for x in env_list))


class DeploymentsTestCase(base_test.BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'
    SITE_NAME = 'test_site'

    def test_get_empty(self):
        result = self.client.deployments.list()
        self.assertEqual(0, len(result))

    def test_create_deployment_illegal_id(self):
        # try id with whitespace
        self.assertRaisesRegex(CloudifyClientError,
                               'contains illegal characters',
                               self.client.deployments.create,
                               'blueprint_id',
                               'illegal deployment id')

    def test_deployment_create_with_overrides(self):
        string_template = 'this_is_a_test_{}'
        string_params = ['visibility', 'description', 'display_name']
        dict_params = ['inputs', 'policy_triggers', 'policy_types', 'outputs',
                       'capabilities', 'resource_tags']
        overrides = {
            "created_at": "2022-08-31T09:47:13.712Z",
            "created_by": "admin",
            "installation_status": "active",
            "deployment_status": "good",
            "workflows": {
                'install': {
                    "name": "install", "plugin": "abc",
                    "operation": "something", "parameters": {},
                    "is_cascading": False, "is_available": True,
                    "availability_rules": None
                },
            },
            "runtime_only_evaluation": False,
            "labels": [],
            'scaling_groups': {
                'group1': {'members': [], 'properties': {}},
            },
        }
        for string_param in string_params:
            overrides[string_param] = string_template.format(string_param)
        for dict_param in dict_params:
            overrides[dict_param] = {
                string_param: string_template.format(string_param)}

        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
            state='uploaded',
            plan={},
        )

        with mock.patch('os.makedirs', return_value=self.tmpdir):
            self.client.deployments.create(
                bp.id,
                deployment_id='dep1',
                # Empty workdir zip
                _workdir_zip='UEsFBgAAAAAAAAAAAAAAAAAAAAAAAA==',
                **overrides
            )
        dep = models.Deployment.query.filter_by(id='dep1').one()
        for param in overrides:
            assert dep[param] == overrides[param]

    def test_put(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        self.assertEqual(deployment_id, self.DEPLOYMENT_ID)
        self.assertEqual(blueprint_id, deployment_response['blueprint_id'])
        self.assertIsNotNone(deployment_response['created_at'])
        self.assertIsNotNone(deployment_response['updated_at'])

    def test_sort_list(self):
        self.put_deployment(deployment_id='d0', blueprint_id='b0')
        self.put_deployment(deployment_id='d1', blueprint_id='b1')

        deployments = self.client.deployments.list(sort='created_at')
        self.assertEqual(2, len(deployments))
        self.assertEqual('d0', deployments[0].id)
        self.assertEqual('d1', deployments[1].id)

        deployments = self.client.deployments.list(
            sort='created_at', is_descending=True)
        self.assertEqual(2, len(deployments))
        self.assertEqual('d1', deployments[0].id)
        self.assertEqual('d0', deployments[1].id)

    def test_put_scaling_groups(self):
        _, _, _, deployment_response = self.put_deployment(
            self.DEPLOYMENT_ID,
            blueprint_file_name='modify3-scale-groups.yaml')
        self.assertIn('group', deployment_response['scaling_groups'])

    def test_delete_blueprint_which_has_deployments(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)
        with self.assertRaises(CloudifyClientError) as context:
            self.client.blueprints.delete(blueprint_id)
        self.assertEqual(400, context.exception.status_code)
        self.assertIn('There exist deployments for this blueprint',
                      str(context.exception))
        self.assertEqual(
            context.exception.error_code,
            manager_exceptions.DependentExistsError.error_code)

    def test_deployment_already_exists(self):
        (blueprint_id,
         deployment_id,
         blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)
        deployment_response = self.put(
            '/deployments/{0}'.format(self.DEPLOYMENT_ID),
            {'blueprint_id': blueprint_id})
        self.assertTrue('already exists' in
                        deployment_response.json['message'])
        self.assertEqual(409, deployment_response.status_code)
        self.assertEqual(deployment_response.json['error_code'],
                         manager_exceptions.ConflictError.error_code)

    def test_get_by_id(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        single_deployment = self.get('/deployments/{0}'
                                     .format(deployment_id)).json
        self.assertEqual(deployment_id, single_deployment['id'])
        self.assertEqual(deployment_response['blueprint_id'],
                         single_deployment['blueprint_id'])
        self.assertEqual(deployment_response['id'],
                         single_deployment['id'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['created_at'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['updated_at'])

    def test_get(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        get_deployments_response = self.client.deployments.list()
        self.assertEqual(1, len(get_deployments_response))
        single_deployment = get_deployments_response[0]
        self.assertEqual(deployment_id, single_deployment['id'])
        self.assertEqual(deployment_response['blueprint_id'],
                         single_deployment['blueprint_id'])
        self.assertEqual(deployment_response['id'],
                         single_deployment['id'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['created_at'])
        self.assertEqual(deployment_response['created_at'],
                         single_deployment['updated_at'])

    def test_get_executions_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        execution = self.client.executions.start(deployment_id, 'install')
        self.assertEqual('install', execution.workflow_id)
        self.assertEqual(blueprint_id, execution['blueprint_id'])
        self.assertEqual(deployment_id, execution.deployment_id)
        self.assertIsNotNone(execution.created_at)
        executions = self.client.executions.list(deployment_id=deployment_id)
        # expecting two executions - 'install' and
        # 'create_deployment_environment'
        self.assertEqual(2, len(executions))
        self.assertIn(execution['id'],
                      [executions[0]['id'], executions[1]['id']])
        self.assertIn('create_deployment_environment',
                      [executions[1]['workflow_id'],
                       executions[0]['workflow_id']])

    def test_executing_nonexisting_workflow(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        try:
            self.client.executions.start(deployment_id,
                                         'nonexisting-workflow-id')
            self.fail()
        except CloudifyClientError as e:
            self.assertEqual(400, e.status_code)
            self.assertEqual(
                manager_exceptions.NonexistentWorkflowError.error_code,
                e.error_code)

    def test_listing_executions_for_nonexistent_deployment(self):
        result = self.client.executions.list(deployment_id='doesnotexist')
        if not isinstance(result, list):
            result = result.items
        assert result == []

    def test_get_workflows_of_deployment(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(
             self.DEPLOYMENT_ID, 'blueprint_with_workflows.yaml')

        resource_path = '/deployments/{0}'.format(deployment_id)
        workflows = self.get(resource_path).json['workflows']
        self.assertEqual(15, len(workflows))
        workflow: Optional[Dict] = next(
            (
                workflow for workflow in workflows
                if workflow['name'] == 'mock_workflow'
            ),
            None,
        )
        assert workflow is not None
        parameters = {
            'optional_param': {'default': 'test_default_value'},
            'mandatory_param': {},
            'mandatory_param2': {},
            'nested_param': {
                'default': {
                    'key': 'test_key',
                    'value': 'test_value'
                }
            }
        }
        self.assertEqual(parameters, workflow['parameters'])

    def test_delete_deployment_verify_nodes_deletion(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        self.assertTrue(len(nodes) > 0)
        nodes_ids = [node['id'] for node in nodes]

        self.delete_deployment(deployment_id)

        # verifying deletion of deployment nodes and executions
        for node_id in nodes_ids:
            resp = self.get('/node-instances/{0}'.format(node_id))
            self.assertEqual(404, resp.status_code)

    def test_delete_deployment_with_live_nodes_without_force_flag(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        # modifying a node's state so there'll be a node in a state other
        # than 'uninitialized'
        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        resp = self.patch('/node-instances/{0}'.format(nodes[0]['id']), {
            'version': 1,
            'state': 'started'
        })
        self.assertEqual(200, resp.status_code)

        # attempting to delete the deployment - should fail because there
        # are live nodes for the deployment

        try:
            self.client.deployments.delete(deployment_id)
        except CloudifyClientError as e:
            self.assertEqual(e.status_code, 400)
            self.assertEqual(
                e.error_code,
                manager_exceptions.DependentExistsError.error_code)

    def test_delete_deployment_with_uninitialized_nodes(self):
        # simulates a deletion of a deployment right after its creation
        # (i.e. all nodes are still in 'uninitialized' state because no
        # execution has yet to take place)
        self._test_delete_deployment_with_nodes_in_certain_state(
            'uninitialized')

    def test_delete_deployment_without_ignore_flag(self):
        # simulates a deletion of a deployment after the uninstall workflow
        # has completed (i.e. all nodes are in 'deleted' state)
        self._test_delete_deployment_with_nodes_in_certain_state('deleted')

    def _test_delete_deployment_with_nodes_in_certain_state(self, state):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        # modifying nodes states
        for node in nodes:
            resp = self.patch('/node-instances/{0}'.format(node['id']), {
                'version': 1,
                'state': state
            })
            self.assertEqual(200, resp.status_code)

        self.client.deployments.delete(deployment_id)

    def test_delete_deployment_with_live_nodes_and_force_flag(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        self.client.deployments.delete(deployment_id, force=True)

    def test_delete_nonexistent_deployment(self):
        # trying to delete a nonexistent deployment
        resp = self.delete('/deployments/nonexistent-deployment')
        self.assertEqual(404, resp.status_code)
        self.assertEqual(
            resp.json['error_code'],
            manager_exceptions.NotFoundError.error_code)

    def test_get_nodes_of_deployment(self):

        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)

        nodes = self.client.node_instances.list(deployment_id=deployment_id)

        self.assertEqual(2, len(nodes))

        def assert_node_exists(starts_with):
            self.assertTrue(
                any(n['id'].startswith(starts_with) for n in nodes),
                'Failed finding node with prefix {0}'.format(starts_with))
        assert_node_exists('vm')
        assert_node_exists('http_web_server')

    def test_delete_deployment_folder_from_file_server(self):
        (blueprint_id, deployment_id, blueprint_response,
         deployment_response) = self.put_deployment(self.DEPLOYMENT_ID)
        config = self.server_configuration
        deployment_folder = os.path.join(config.file_server_root,
                                         FILE_SERVER_DEPLOYMENTS_FOLDER,
                                         DEFAULT_TENANT_NAME,
                                         deployment_id)
        try:
            os.makedirs(deployment_folder)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(deployment_folder):
                pass
            else:
                raise
        deployment_resource_path = os.path.join(deployment_folder, 'test.txt')
        with open(deployment_resource_path, 'w') as f:
            f.write('deployment resource')

        self.delete_deployment(deployment_id)
        self.assertFalse(os.path.exists(deployment_folder))

    def test_inputs(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs.yaml',
            blueprint_id='b5566',
            deployment_id='dep1',
            inputs={'http_web_server_port': '8080',
                    'http_web_server_port2': {'a': ['9090']}})
        node = self.client.nodes.get('dep1', 'http_web_server')
        self.assertEqual('8080', node.properties['port'])
        node2 = self.client.nodes.get('dep1', 'http_web_server2')
        self.assertEqual('9090', node2.properties['port'])
        with self.assertRaisesRegex(
                CloudifyClientError, 'inputs parameter is expected'):
            self.put_deployment(
                deployment_id='dep2',
                blueprint_id='b1122',
                blueprint_file_name='blueprint_with_inputs.yaml',
                inputs='illegal'
            )
        with self.assertRaises(MissingRequiredDeploymentInputError):
            self.put_deployment(
                deployment_id='dep2',
                blueprint_id='b3344',
                blueprint_file_name='blueprint_with_inputs.yaml',
                inputs={'some_input': '1234'}
            )
        with self.assertRaises(CloudifyClientError):
            self.put_deployment(
                deployment_id='dep2',
                blueprint_id='b7788',
                blueprint_file_name='blueprint_with_inputs'
                                    '.yaml',
                inputs={
                    'http_web_server_port': '1234',
                    'http_web_server_port2': {'a': ['9090']},
                    'unknown_input': 'yay'
                }
            )
        with self.assertRaises(dsl_exceptions.InputEvaluationError):
            self.put_deployment(
                deployment_id='dep2',
                blueprint_id='b7789',
                blueprint_file_name='blueprint_with_inputs'
                                    '.yaml',
                inputs={
                    'http_web_server_port': '1234',
                    'http_web_server_port2': {
                        'something_new': ['9090']}
                }
            )
        with self.assertRaisesRegex(dsl_exceptions.InputEvaluationError,
                                    'expected to be an int'):
            self.put_deployment(
                deployment_id='dep2',
                blueprint_id='b7790',
                blueprint_file_name='blueprint_with_inputs'
                                    '.yaml',
                inputs={
                    'http_web_server_port': '1234',
                    'http_web_server_port2': [1234]
                }
            )
        with self.assertRaisesRegex(dsl_exceptions.InputEvaluationError,
                                    "(List size of).+(but index)"):
            self.put_deployment(
                deployment_id='dep2',
                blueprint_id='b7791',
                blueprint_file_name='blueprint_with_inputs'
                                    '.yaml',
                inputs={
                    'http_web_server_port': '1234',
                    'http_web_server_port2': {'a': []}
                }
            )

    def test_input_with_default_value_and_constraints(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs_and_constraints.yaml',
            blueprint_id='b9700',
            deployment_id=self.DEPLOYMENT_ID)
        node = self.client.nodes.get(self.DEPLOYMENT_ID, 'http_web_server')
        self.assertEqual('8080', node.properties['port'])

    def test_input_with_constraints_and_value_provided(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs_and_constraints.yaml',
            blueprint_id='b9701',
            deployment_id=self.DEPLOYMENT_ID,
            inputs={'http_web_server_port': '9090'})
        node = self.client.nodes.get(
            self.DEPLOYMENT_ID, 'http_web_server')
        self.assertEqual('9090', node.properties['port'])

    def test_input_violates_constraint(self):
        with self.assertRaisesRegex(
                dsl_exceptions.ConstraintException,
                '123 .* http_web_server_port .* constraint'):
            filename = 'blueprint_with_inputs_and_constraints.yaml'
            self.put_deployment(
                blueprint_id='b9702',
                blueprint_file_name=filename,
                deployment_id=self.DEPLOYMENT_ID,
                inputs={'http_web_server_port': '123'}
            )

    def test_input_violates_constraint_data_type(self):
        with self.assertRaises(dsl_exceptions.ConstraintException):
            filename = 'blueprint_with_inputs_and_constraints.yaml'
            self.put_deployment(
                blueprint_id='b9702',
                blueprint_file_name=filename,
                deployment_id=self.DEPLOYMENT_ID,
                inputs={'http_web_server_port': 123}
            )

    def test_outputs(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_with_outputs.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        instances = self.client.node_instances.list(deployment_id=id_)

        vm = [x for x in instances if x.node_id == 'vm'][0]
        vm_props = {'ip': '10.0.0.1'}
        self.client.node_instances.update(vm.id, runtime_properties=vm_props)

        ws = [x for x in instances if x.node_id == 'http_web_server'][0]
        ws_props = {'port': 8080}
        self.client.node_instances.update(ws.id, runtime_properties=ws_props)

        response = self.client.deployments.outputs.get(id_)
        self.assertEqual(id_, response.deployment_id)
        outputs = response.outputs

        self.assertTrue('ip_address' in outputs)
        self.assertTrue('port' in outputs)
        self.assertEqual('10.0.0.1', outputs['ip_address'])
        self.assertEqual(80, outputs['port'])

        dep = self.client.deployments.get(id_)
        self.assertEqual('Web site IP address.',
                         dep.outputs['ip_address']['description'])
        self.assertEqual('Web site port.', dep.outputs['port']['description'])

        endpoint = outputs['endpoint']

        self.assertEqual('http', endpoint['type'])
        self.assertEqual('10.0.0.1', endpoint['ip'])
        self.assertEqual(8080, endpoint['port'])
        self.assertEqual(81, outputs['port2'])

    def test_illegal_output(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint_with_illegal_output.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        outputs = self.client.deployments.outputs.get(id_)
        self.assertIn("More than one node instance found for node",
                      outputs['outputs']['ip_address'])

    def test_no_outputs(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='blueprint.yaml',
            blueprint_id=id_,
            deployment_id=id_)
        outputs = self.client.deployments.outputs.get(id_)
        self.assertEqual(outputs['outputs'], {})

    def test_creation_failure_when_plugin_not_found_central_deployment(self):
        from cloudify_rest_client.exceptions import DeploymentPluginNotFound
        id_ = 'i{0}'.format(uuid.uuid4())
        with self.assertRaises(DeploymentPluginNotFound) as cm:
            self.put_deployment(
                blueprint_file_name='deployment_with_source_plugin.yaml',
                blueprint_id=id_,
                deployment_id=id_)

        self.assertEqual(400, cm.exception.status_code)
        self.assertEqual(
            manager_exceptions.DeploymentPluginNotFound.error_code,
            cm.exception.error_code)

    def test_creation_failure_when_plugin_not_found_host_agent(self):
        from cloudify_rest_client.exceptions import DeploymentPluginNotFound
        id_ = 'i{0}'.format(uuid.uuid4())
        with self.assertRaises(DeploymentPluginNotFound) as cm:
            self.put_deployment(
                blueprint_file_name='deployment_'
                                    'with_source_plugin_host_agent.yaml',
                blueprint_id=id_,
                deployment_id=id_)
        self.assertEqual(400, cm.exception.status_code)
        self.assertEqual(
            manager_exceptions.DeploymentPluginNotFound.error_code,
            cm.exception.error_code)

    def test_creation_success_when_source_plugin_exists_on_manager(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION).json
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_'
                                'existing_plugin_on_manager.yaml',
            blueprint_id=id_,
            deployment_id=id_)

    def test_creation_success_when_source_plugin_with_address_exists(self):
        self.upload_plugin(TEST_PACKAGE_NAME, TEST_PACKAGE_VERSION).json
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_source_address.yaml',
            blueprint_id=id_,
            deployment_id=id_)

    def test_creation_success_when_plugin_not_found_with_new_flag(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_source_plugin.yaml',
            blueprint_id=id_,
            deployment_id=id_,
            skip_plugins_validation=True)

    def test_creation_failure_with_invalid_flag_argument(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        with self.assertRaises(CloudifyClientError) as cm:
            self.put_deployment(
                blueprint_file_name='deployment_with_source_plugin.yaml',
                blueprint_id=id_,
                deployment_id=id_,
                skip_plugins_validation='invalid_arg')
        self.assertEqual(400, cm.exception.status_code)
        self.assertEqual(manager_exceptions.BadParametersError.error_code,
                         cm.exception.error_code)

    def test_creation_failure_without_skip_plugins_validation_argument(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_blueprint('mock_blueprint',
                           'deployment_with_source_plugin.yaml', id_)
        response = self.put('/deployments/{}'.format(id_),
                            {'blueprint_id': id_})
        self.assertEqual('deployment_plugin_not_found',
                         response.json['error_code'])
        self.assertEqual('400 BAD REQUEST', response.status)
        self.assertEqual(400, response.status_code)

    def test_creation_success_when_diamond_plugin_in_blueprint(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_'
                                'diamond_as_source_plugin.yaml',
            blueprint_id=id_,
            deployment_id=id_)

    def test_creation_success_when_diamond_as_host_agent_in_blueprint(self):
        id_ = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(
            blueprint_file_name='deployment_with_'
                                'diamond_as_host_agent.yaml',
            blueprint_id=id_,
            deployment_id=id_)

    def test_creation_success_without_site(self):
        self._put_deployment_without_site()

    def test_creation_success_with_site(self):
        self.client.sites.create(self.SITE_NAME)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id,
                            site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)

    def test_creation_success_with_different_site_visibility(self):
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.GLOBAL)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id,
                            site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)
        self.assertEqual(deployment.visibility, VisibilityState.TENANT)

    def test_creation_failure_invalid_site_visibility(self):
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.PRIVATE)
        resource_id = 'i{0}'.format(uuid.uuid4())
        error_msg = "400: The visibility of deployment `{0}`: `tenant` " \
                    "can't be wider than the visibility of it's site " \
                    "`{1}`: `private`".format(resource_id, self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id=resource_id,
                               deployment_id=resource_id,
                               site_name=self.SITE_NAME)

    def test_creation_failure_invalid_site(self):
        error_msg = '404: Requested `Site` with ID `test_site` was not found'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id='i{0}'.format(uuid.uuid4()),
                               deployment_id='i{0}'.format(uuid.uuid4()),
                               site_name=self.SITE_NAME)

        error_msg = '400: The `site_name` argument contains illegal ' \
                    'characters.'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.put_deployment,
                               blueprint_file_name='blueprint.yaml',
                               blueprint_id='i{0}'.format(uuid.uuid4()),
                               deployment_id='i{0}'.format(uuid.uuid4()),
                               site_name=':invalid_site')

    def test_set_site_deployment_created_without_site(self):
        resource_id = self._put_deployment_without_site()
        self.client.sites.create(self.SITE_NAME)
        self.client.deployments.set_site(resource_id, site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)

        # Setting a site after a previous one was set
        new_site_name = 'new_site'
        self.client.sites.create(new_site_name, location="34.0,32.0")
        self.client.deployments.set_site(resource_id, site_name=new_site_name)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, new_site_name)

    def test_set_site_deployment_created_with_site(self):
        resource_id = self._put_deployment_with_site()

        # Setting a site after the deployment was created with a site
        new_site_name = 'new_site'
        self.client.sites.create(new_site_name, location="34.0,32.0")
        self.client.deployments.set_site(resource_id, site_name=new_site_name)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, new_site_name)

    def test_set_site_different_visibility(self):
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.GLOBAL)
        resource_id = self._put_deployment_without_site()
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.visibility, VisibilityState.TENANT)
        self.client.deployments.set_site(resource_id, site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)

    def test_set_site_invalid_deployment_visibility(self):
        resource_id = self._put_deployment_without_site()
        self.client.sites.create(self.SITE_NAME,
                                 visibility=VisibilityState.PRIVATE)
        error_msg = "400: The visibility of deployment `{0}`: `tenant` " \
                    "can't be wider than the visibility of it's site " \
                    "`{1}`: `private`".format(resource_id, self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               resource_id,
                               site_name=self.SITE_NAME)

    def test_set_site_invalid_deployment(self):
        error_msg = '404: Requested `Deployment` with ID `no_deployment` ' \
                    'was not found'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               'no_deployment',
                               site_name=self.SITE_NAME)

    def test_set_site_invalid_site(self):
        resource_id = self._put_deployment_without_site()
        error_msg = '404: Requested `Site` with ID `{0}` was not ' \
                    'found'.format(self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               resource_id,
                               site_name=self.SITE_NAME)

        error_msg = '400: The `site_name` argument contains illegal ' \
                    'characters.'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               deployment_id='i{0}'.format(uuid.uuid4()),
                               site_name=':invalid_site')

    def test_set_site_bad_parameters(self):
        resource_id = self._put_deployment_without_site()
        error_msg = '400: Must provide either a `site_name` of a valid site ' \
                    'or `detach_site` with true value for detaching the ' \
                    'current site of the given deployment'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               deployment_id=resource_id)
        self.client.sites.create(self.SITE_NAME)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.set_site,
                               deployment_id=resource_id,
                               site_name=self.SITE_NAME,
                               detach_site=True)

    def test_set_site_detach_existing_site(self):
        resource_id = self._put_deployment_with_site()

        # Detaching the site when the deployment is assigned with one
        self.client.deployments.set_site(resource_id, detach_site=True)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)

    def test_set_site_detach_none_site(self):
        # Detaching the site when the deployment is not assigned with one
        resource_id = self._put_deployment_without_site()
        self.client.deployments.set_site(resource_id, detach_site=True)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)

    def test_delete_site_of_deployment(self):
        resource_id = self._put_deployment_with_site()

        # Delete a site that is attached to the deployment
        self.client.sites.delete(self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)
        error_msg = '404: Requested `Site` with ID `test_site` was not found'
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.sites.get,
                               self.SITE_NAME)

    def test_delete_deployment_attached_to_site(self):
        resource_id = self._put_deployment_with_site()

        # Delete a deployment that is attached to a site
        self.delete_deployment(resource_id)

        # self.client.deployments.delete(resource_id, delete_db_mode=True)
        site = self.client.sites.get(self.SITE_NAME)
        self.assertEqual(site.name, self.SITE_NAME)
        error_msg = '404: Requested `Deployment` with ID `{}` ' \
                    'was not found'.format(resource_id)
        self.assertRaisesRegex(CloudifyClientError,
                               error_msg,
                               self.client.deployments.get,
                               resource_id)

    def _put_deployment_without_site(self):
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id)
        deployment = self.client.deployments.get(resource_id)
        self.assertIsNone(deployment.site_name)
        return resource_id

    def _put_deployment_with_site(self):
        self.client.sites.create(self.SITE_NAME)
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.put_deployment(blueprint_file_name='blueprint.yaml',
                            blueprint_id=resource_id,
                            deployment_id=resource_id,
                            site_name=self.SITE_NAME)
        deployment = self.client.deployments.get(resource_id)
        self.assertEqual(deployment.site_name, self.SITE_NAME)
        return resource_id

    def test_list_deployments_with_filter_id(self):
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        dep1 = models.Deployment(
            id='dep1',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        dep2 = models.Deployment(
            id='dep2',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        dep1.labels = [
            models.DeploymentLabel(
                key='key1',
                value='value1',
                creator=self.user,
            ),
        ]
        dep2.labels = [
            models.DeploymentLabel(
                key='key1',
                value='value2',
                creator=self.user,
            ),
        ]
        self.client.deployments_filters.create(
            filter_id='filter1',
            filter_rules=[
                {
                    'key': 'key1',
                    'values': ['value1'],
                    'operator': 'any_of',
                    'type': 'label',
                },
            ],
        )
        deployments = self.client.deployments.list(filter_id='filter1')
        assert len(deployments) == 1
        assert deployments[0].id == dep1.id
        assert deployments.metadata['filtered'] == 1

    def test_update_attributes(self):
        self.put_blueprint()
        bp = self.sm.get(models.Blueprint, 'blueprint')
        self.sm.put(models.Deployment(
            id='dep1',
            display_name='dep1',
            blueprint=bp,
            created_at=datetime.utcnow()
        ))
        new_attributes = {
            'description': 'descr1',
            'workflows': {'wf1': {}},
            'inputs': {'input1': {}},
            'policy_types': ['type1'],
            'policy_triggers': {'trigger1': {}},
            'groups': {'group1': {}},
            'scaling_groups':
                {'scaling_group1': {'members': [], 'properties': {}}},
            'outputs': {'output1': {}},
            'capabilities': {'cap1': {}}
        }
        self.client.deployments.set_attributes('dep1', **new_attributes)
        dep = self.sm.get(models.Deployment, 'dep1')
        for k, v in new_attributes.items():
            assert getattr(dep, k) == v

    def test_update_attributes_already_set(self):
        self.put_blueprint()
        bp = self.sm.get(models.Blueprint, 'blueprint')
        self.sm.put(models.Deployment(
            id='dep1',
            display_name='dep1',
            blueprint=bp,
            description='d1',
            created_at=datetime.utcnow()
        ))
        with self.assertRaisesRegex(CloudifyClientError, 'already set'):
            self.client.deployments.set_attributes('dep1', description='d2')

    def test_create_deployment_with_default_groups(self):
        _, _, _, deployment = self.put_deployment(
            blueprint_file_name='blueprint_with_default_groups.yaml',
            inputs={'inp1': 'g3'}
        )

        dep = self.sm.get(models.Deployment, deployment.id)
        groups = dep.deployment_groups
        assert len(groups) == 2
        assert {g.id for g in groups} == {'g1', 'g3'}

    def test_create_deployment_with_default_schedules(self):
        _, _, _, deployment = self.put_deployment(
            blueprint_file_name='blueprint_with_default_schedules.yaml',
            inputs={'param1': 'value2'})

        sched_ids = list(self.client.execution_schedules.list(
            _include=['id', 'deployment_id']))
        self.assertListEqual(
            sched_ids,
            [{'id': 'sc1', 'deployment_id': deployment.id},
             {'id': 'sc2', 'deployment_id': deployment.id}])

        sc1 = self.client.execution_schedules.get('sc1', deployment.id)
        self.assertEqual(sc1['rule']['recurrence'], '1w')
        self.assertEqual(len(sc1['all_next_occurrences']), 5)
        self.assertEqual(sc1['parameters'], {'param1': 'value2'})

    def test_list_deployments_with_not_empty_filter(self):
        self.client.sites.create(self.SITE_NAME)
        _, _, _, dep_1 = self.put_deployment(
            blueprint_id='dep_with_site',
            deployment_id='dep_with_site',
            site_name=self.SITE_NAME)

        _, _, _, dep_2 = self.put_deployment(
            blueprint_id='dep_with_no_site',
            deployment_id='dep_with_no_site')

        site_name_filter = \
            FilterRule('site_name', [], 'is_not_empty', 'attribute')
        filtered_dep_ids = [d['id'] for d in self.client.deployments.list(
            filter_rules=[site_name_filter])]
        self.assertListEqual(filtered_dep_ids, ['dep_with_site'])

    def test_list_deployments_with_schedules_filter(self):
        _, _, _, dep_1 = self.put_deployment(
            blueprint_id='born-with-schedules',
            deployment_id='born-with-schedules',
            blueprint_file_name='blueprint_with_default_schedules.yaml')
        _, _, _, dep_2 = self.put_deployment(
            blueprint_id='born-without-schedules',
            deployment_id='born-without-schedules')
        schedules_filter = \
            FilterRule('schedules', [], 'is_not_empty', 'attribute')

        # dep_1 has has 2 schedules, dep_2 has none
        filtered_dep_ids = [d['id'] for d in self.client.deployments.list(
            filter_rules=[schedules_filter])]
        self.assertListEqual(filtered_dep_ids, ['born-with-schedules'])

        self.client.execution_schedules.create(
            'custom-sc', dep_2.id, 'install', since=datetime.utcnow(), count=1)
        self.client.execution_schedules.delete('sc1', dep_1.id)

        # now each deployment has 1 schedule
        filtered_dep_ids = [d['id'] for d in self.client.deployments.list(
            filter_rules=[schedules_filter])]
        self.assertListEqual(filtered_dep_ids, ['born-with-schedules',
                                                'born-without-schedules'])

        self.client.execution_schedules.delete('sc2', dep_1.id)
        filtered_dep_ids = [d['id'] for d in self.client.deployments.list(
            filter_rules=[schedules_filter])]
        self.assertListEqual(filtered_dep_ids, ['born-without-schedules'])

    def test_list_deployments_with_schedules_filter_bad_operator(self):
        _, _, _, dep_1 = self.put_deployment(
            blueprint_id='born-with-schedules',
            deployment_id='born-with-schedules',
            blueprint_file_name='blueprint_with_default_schedules.yaml')
        schedules_filter = \
            FilterRule('schedules', ['sched-1'], 'any_of', 'attribute')
        self.assertRaisesRegex(
            CloudifyClientError,
            "400:.* only possible with the is_not_empty operator",
            self.client.deployments.list,
            filter_rules=[schedules_filter])

    def test_create_deployment_with_display_name(self):
        display_name = 'New Deployment'
        _, _, _, deployment = self.put_deployment(display_name=display_name)
        self.assertEqual(deployment.display_name, display_name)

    def test_deployment_display_name_is_normalized(self):
        _, _, _, deployment = self.put_deployment(
            display_name='ab\u004f\u0301cd')
        self.assertEqual(deployment.display_name, 'ab\u00d3cd')

    def test_deployment_display_name_defaults_to_id(self):
        _, _, _, deployment = self.put_deployment('dep1')
        self.assertEqual(deployment.display_name, 'dep1')

    def test_deployment_display_name_not_unique(self):
        display_name = 'New Deployment'
        _, _, _, dep1 = self.put_deployment(deployment_id='dep1',
                                            blueprint_id='bp1',
                                            display_name=display_name)
        _, _, _, dep2 = self.put_deployment(deployment_id='dep2',
                                            blueprint_id='bp2',
                                            display_name=display_name)
        self.assertEqual(dep1.display_name, display_name)
        self.assertEqual(dep2.display_name, display_name)

    def test_deployment_display_name_with_control_chars_fails(self):
        self.assertRaisesRegex(
            ValueError,
            'contains illegal characters',
            self.put_deployment,
            display_name='ab\u0000cd')

    def test_deployments_list_search_by_display_name(self):
        dep1_name = 'Dep$lo(y.m_e#nt 1'
        dep2_name = 'D\\e%pl\u004f\u0301y/me&n*t 2'
        _, _, _, dep1 = self.put_deployment(deployment_id='dep1',
                                            blueprint_id='bp1',
                                            display_name=dep1_name)
        _, _, _, dep2 = self.put_deployment(deployment_id='dep2',
                                            blueprint_id='bp2',
                                            display_name=dep2_name)
        dep_list_1 = self.client.deployments.list(_search='dep1',
                                                  _search_name=dep1_name)
        self.assertEqual(len(dep_list_1), 1)
        self.assertEqual(dep_list_1[0].id, dep1.id)
        dep_list_2 = self.client.deployments.list(_search_name=dep2_name)
        self.assertEqual(len(dep_list_2), 1)
        self.assertEqual(dep_list_2[0].id, dep2.id)

    def test_display_name_from_dsl(self):
        self.put_deployment(
            deployment_id='dep1',
            blueprint_file_name='blueprint_with_display_name.yaml'
        )
        dep = self.sm.get(models.Deployment, 'dep1')
        assert dep.display_name == 'y'

    def test_set_visibility(self):
        self.put_deployment(
            deployment_id='d',
            blueprint_file_name='blueprint.yaml'
        )
        dep = self.sm.get(models.Deployment, 'd')
        assert dep.visibility == VisibilityState.TENANT
        for node in self.sm.list(models.Node, filters={'deployment_id': 'd'}):
            assert node.visibility == VisibilityState.TENANT

        self.client.blueprints.set_visibility(
            'blueprint', VisibilityState.GLOBAL)
        self.client.deployments.set_visibility('d', VisibilityState.GLOBAL)

        assert dep.visibility == VisibilityState.GLOBAL
        for node in self.sm.list(models.Node, filters={'deployment_id': 'd'}):
            assert node.visibility == VisibilityState.GLOBAL

    def test_set_visibility_same_node_ids_succeed(self):
        self.put_deployment(
            deployment_id='d1',
            blueprint_id='bp1',
            blueprint_file_name='blueprint.yaml'
        )
        self.put_deployment(
            deployment_id='d2',
            blueprint_id='bp2',
            blueprint_file_name='blueprint.yaml'
        )
        dep1 = self.sm.get(models.Deployment, 'd1')
        dep2 = self.sm.get(models.Deployment, 'd2')
        assert dep1.visibility == VisibilityState.TENANT
        assert dep2.visibility == VisibilityState.TENANT

        self.client.blueprints.set_visibility('bp1', VisibilityState.GLOBAL)
        self.client.blueprints.set_visibility('bp2', VisibilityState.GLOBAL)
        self.client.deployments.set_visibility('d1', VisibilityState.GLOBAL)
        self.client.deployments.set_visibility('d2', VisibilityState.GLOBAL)
        assert dep1.visibility == VisibilityState.GLOBAL
        assert dep2.visibility == VisibilityState.GLOBAL


class DeploymentsDeleteTest(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        self.blueprint = models.Blueprint(
            id='bp1',
            tenant=self.tenant,
            creator=self.user,
        )
        self.deployment = models.Deployment(
            id='dep1',
            blueprint=self.blueprint,
            tenant=self.tenant,
            creator=self.user,
        )

    def test_deleted_on_success(self):
        delete_exc = self.deployment.make_delete_environment_execution()
        self.sm.put(delete_exc)
        self.client.executions.update(delete_exc.id, ExecutionState.TERMINATED)
        assert models.Deployment.query.count() == 0

    def test_not_deleted_on_fail(self):
        delete_exc = self.deployment.make_delete_environment_execution()
        self.sm.put(delete_exc)
        self.client.executions.update(delete_exc.id, ExecutionState.FAILED)
        assert models.Deployment.query.count() == 1

    def test_not_deleted_on_cancel(self):
        delete_exc = self.deployment.make_delete_environment_execution()
        self.sm.put(delete_exc)
        self.client.executions.update(delete_exc.id, ExecutionState.CANCELLED)
        assert models.Deployment.query.count() == 1

    def test_deleted_fail_with_force(self):
        delete_exc = self.deployment.make_delete_environment_execution(
            force=True)
        self.sm.put(delete_exc)
        self.client.executions.update(delete_exc.id, ExecutionState.FAILED)
        assert models.Deployment.query.count() == 0

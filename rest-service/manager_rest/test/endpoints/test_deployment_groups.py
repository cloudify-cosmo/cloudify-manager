import mock

from datetime import datetime

from cloudify.models_states import VisibilityState, ExecutionState
from cloudify_rest_client.exceptions import CloudifyClientError

from manager_rest.manager_exceptions import SQLStorageException

from manager_rest.storage import models

from manager_rest.test import base_test


@mock.patch(
    'manager_rest.rest.resources_v3_1.deployments.workflow_sendhandler',
    mock.Mock()
)
class DeploymentGroupsTestCase(base_test.BaseServerTestCase):
    def setUp(self):
        super(DeploymentGroupsTestCase, self).setUp()
        self.put_blueprint()
        self.client.deployments.create('blueprint', 'dep1')
        self.client.deployments.create('blueprint', 'dep2')

    def test_get_empty(self):
        result = self.client.deployment_groups.list()
        assert len(result) == 0

    def test_add_empty_group(self):
        result = self.client.deployment_groups.list()
        assert len(result) == 0
        result = self.client.deployment_groups.put('group1')
        assert result['id'] == 'group1'

    def test_add_to_group(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        assert set(group['deployment_ids']) == {'dep1', 'dep2'}

    def test_overwrite_group(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

    def test_clear_group(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=[]
        )
        assert group['deployment_ids'] == []

    def test_update_description(self):
        """When deployment_ids is not provided, the group is not cleared"""
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group['deployment_ids'] == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            description='descr'
        )
        assert group['description'] == 'descr'
        assert group['deployment_ids'] == ['dep1']

    def test_create_with_blueprint(self):
        self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint',
            default_inputs={'a': 'b'}
        )
        group = self.sm.get(models.DeploymentGroup, 'group1')
        assert group.default_blueprint.id == 'blueprint'
        assert group.default_inputs == {'a': 'b'}

    def test_set_visibility(self):
        self.client.deployment_groups.put(
            'group1',
            visibility=VisibilityState.PRIVATE
        )
        group = self.sm.get(models.DeploymentGroup, 'group1')
        assert group.visibility == VisibilityState.PRIVATE

        self.client.deployment_groups.put(
            'group1',
            visibility=VisibilityState.TENANT
        )
        assert group.visibility == VisibilityState.TENANT

        with self.assertRaisesRegex(
                CloudifyClientError, 'visibility_states') as cm:
            self.client.deployment_groups.put(
                'group1',
                visibility='invalid visibility'
            )
        assert cm.exception.status_code == 409

    def test_create_deployment(self):
        self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint',
            new_deployments=[{}]
        )
        group = self.sm.get(models.DeploymentGroup, 'group1')
        assert len(group.deployments) == 1
        dep = group.deployments[0]
        assert dep.blueprint.id == 'blueprint'
        assert dep.id == 'group1-1'

    def test_add_deployments(self):
        group = self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint',
            deployment_ids=['dep1']
        )
        assert set(group.deployment_ids) == {'dep1'}
        group = self.client.deployment_groups.put(
            'group1',
            new_deployments=[{}]
        )
        assert set(group.deployment_ids) == {'dep1', 'group1-2'}
        group = self.client.deployment_groups.put(
            'group1',
            new_deployments=[{}]
        )
        assert set(group.deployment_ids) == {'dep1', 'group1-2', 'group1-3'}

    def test_create_from_spec(self):
        self.put_blueprint(
            blueprint_file_name='blueprint_with_inputs.yaml',
            blueprint_id='bp_with_inputs')
        inputs = {'http_web_server_port': 1234}
        labels = [{'label1': 'label-value'}]
        group = self.client.deployment_groups.put(
            'group1',
            blueprint_id='bp_with_inputs',
            new_deployments=[
                {
                    'id': 'spec_dep1',
                    'inputs': inputs,
                    'labels': labels,
                }
            ]
        )

        assert set(group.deployment_ids) == {'spec_dep1'}
        deps = self.sm.get(models.DeploymentGroup, 'group1').deployments
        assert len(deps) == 1
        create_exec_params = deps[0].create_execution.parameters
        assert create_exec_params['inputs'] == inputs
        assert create_exec_params['labels'] == [('label1', 'label-value')]

    def test_add_deployment_ids(self):
        self.client.deployment_groups.put('group1')
        group = self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']
        group = self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep2']
        )
        assert set(group.deployment_ids) == {'dep1', 'dep2'}

    def test_add_twice(self):
        self.client.deployment_groups.put('group1')
        group = self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']
        group = self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']

    def test_remove_nonexistent(self):
        self.client.deployment_groups.put('group1')
        with self.assertRaisesRegexp(CloudifyClientError, 'not found'):
            self.client.deployment_groups.remove_deployments(
                'group1',
                deployment_ids=['nonexistent']
            )

    def test_remove_deployment_ids(self):
        self.client.deployment_groups.put('group1')
        group = self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        assert set(group.deployment_ids) == {'dep1', 'dep2'}
        group = self.client.deployment_groups.remove_deployments(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep2']

    def test_add_deployment_count(self):
        self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint'
        )
        group = self.client.deployment_groups.add_deployments(
            'group1',
            count=3
        )
        assert len(group.deployment_ids) == 3

    def test_add_remove_same(self):
        self.client.deployment_groups.put('group1')
        group = self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1']
        )
        # add and remove the same deployment in a single call - it is
        # removed; using the http client directly, because the restclient
        # has no way to express such inconsistency
        self.client.deployment_groups.api.patch(
            '/deployment-groups/{0}'.format(group['id']),
            data={
                'add': {
                    'deployment_ids': ['dep2']
                },
                'remove': {
                    'deployment_ids': ['dep1', 'dep2']
                },
            }
        )
        group = self.client.deployment_groups.get(group['id'])
        assert group.deployment_ids == []

    def test_add_inputs(self):
        self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint'
        )
        group = self.client.deployment_groups.add_deployments(
            'group1',
            new_deployments=[{}, {}]
        )
        assert len(group.deployment_ids) == 2

    def test_get_deployment(self):
        """Group IDs are also in the deployment response"""
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        self.client.deployment_groups.put(
            'group2',
            deployment_ids=['dep1']
        )
        dep = self.client.deployments.get('dep1')
        assert set(dep.deployment_groups) == {'group1', 'group2'}

    def test_get_deployment_include(self):
        """Group IDs are also in the deployment response"""
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        self.client.deployment_groups.put(
            'group2',
            deployment_ids=['dep1']
        )
        dep = self.client.deployments.get(
            'dep1',
            _include=['id', 'deployment_groups'])
        assert set(dep.deployment_groups) == {'group1', 'group2'}

    def test_get_deployment_by_group(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        deployments = self.client.deployments.list(_group_id='group1')
        assert len(deployments) == 1
        assert deployments[0].id == 'dep1'

    def test_group_delete(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert len(group.deployment_ids) == 1
        group = self.client.deployment_groups.delete('group1')
        assert len(self.client.deployment_groups.list()) == 0
        # deleting the group didn't delete the deployments themselves
        assert len(self.client.deployments.list()) == 2

    def test_group_delete_deployments(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        self.client.deployment_groups.delete(
            'group1', delete_deployments=True)
        assert len(self.client.deployment_groups.list()) == 0

        # dep hasnt been deleted _yet_, but check that delete-dep-env for it
        # was run
        dep = self.sm.get(models.Deployment, 'dep1')
        assert len(dep.executions) == 2
        assert any(exc.workflow_id == 'delete_deployment_environment'
                   for exc in dep.executions)

    def test_create_filters(self):
        """Create a group with filter_id to set the deployments"""
        self.client.deployments.update_labels('dep1', [
            {'label1': 'value1'}
        ])
        self.client.deployments_filters.create('filter1', [
            {'key': 'label1', 'values': ['value1'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployment_groups.put(
            'group1',
            filter_id='filter1'
        )
        group = self.client.deployment_groups.get('group1')
        assert group.deployment_ids == ['dep1']

    def test_add_from_filters(self):
        """Extend a group providing filter_id"""
        self.client.deployments.update_labels('dep1', [
            {'label1': 'value1'}
        ])
        self.client.deployments_filters.create('filter1', [
            {'key': 'label1', 'values': ['value1'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployment_groups.put('group1')
        self.client.deployment_groups.add_deployments(
            'group1',
            filter_id='filter1'
        )
        group = self.client.deployment_groups.get('group1')
        assert group.deployment_ids == ['dep1']

    def test_remove_from_filters(self):
        """Shrink a group providing filter_id"""
        self.client.deployments.update_labels('dep1', [
            {'label1': 'value1'}
        ])
        self.client.deployments_filters.create('filter1', [
            {'key': 'label1', 'values': ['value1'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        self.client.deployment_groups.remove_deployments(
            'group1',
            filter_id='filter1'
        )
        group = self.client.deployment_groups.get('group1')
        assert group.deployment_ids == []

    def test_add_from_group(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        self.client.deployment_groups.put(
            'group2',
            deployment_ids=['dep2']
        )
        group3 = self.client.deployment_groups.put(
            'group3',
            deployments_from_group='group1'
        )
        assert set(group3.deployment_ids) == {'dep1'}
        group3 = self.client.deployment_groups.add_deployments(
            'group3',
            deployments_from_group='group2'
        )
        assert set(group3.deployment_ids) == {'dep1', 'dep2'}

    def test_remove_by_group(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        self.client.deployment_groups.put(
            'group2',
            deployment_ids=['dep1']
        )
        group1 = self.client.deployment_groups.remove_deployments(
            'group1',
            deployments_from_group='group2'
        )
        assert set(group1.deployment_ids) == {'dep2'}
        # removing is idempotent
        group1 = self.client.deployment_groups.remove_deployments(
            'group1',
            deployments_from_group='group2'
        )
        assert set(group1.deployment_ids) == {'dep2'}

    def test_set_labels(self):
        """Create a group with labels"""
        labels = [{'label1': 'value1'}]
        updated_labels = [{'label1': 'value2'}, {'label2': 'value3'}]
        group = self.client.deployment_groups.put(
            'group1',
            labels=labels,
        )
        self.assert_resource_labels(group.labels, labels)
        group = self.client.deployment_groups.put(
            'group1',
            labels=updated_labels,
        )
        self.assert_resource_labels(group.labels, updated_labels)

    def test_group_labels_for_deployments(self):
        """Group labels are applied to the newly-created deployments"""
        group = self.client.deployment_groups.put(
            'group1',
            labels=[{'label1': 'value1'}, {'label2': 'value2'}],
            blueprint_id='blueprint',
            new_deployments=[{
                'labels': [{'label1': 'value1'}, {'label1': 'value2'},
                           {'label3': 'value4'}]
            }]
        )
        dep_id = group.deployment_ids[0]
        dep = self.sm.get(models.Deployment, dep_id)
        self.create_deployment_environment(dep)
        client_dep = self.client.deployments.get(dep_id)
        self.assert_resource_labels(client_dep.labels, [
            # labels from both the group, and the deployment
            # (note that label1=value1 occurs in both places)
            {'label1': 'value1'}, {'label1': 'value2'}, {'label2': 'value2'},
            {'label3': 'value4'},
        ])

    def test_delete_group_label(self):
        """Deleting a label from the group, deletes it from its deps"""
        self.client.deployments.update_labels('dep1', [{'label1': 'value1'}])
        self.client.deployment_groups.put(
            'group1',
            labels=[{'label1': 'value1'}],
        )
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        group = self.client.deployment_groups.put(
            'group1',
            labels=[]
        )
        assert group.labels == []
        client_dep = self.client.deployments.get('dep1')
        assert client_dep.labels == []

    def test_add_group_label(self):
        """Adding a label to a group with deps, adds it to the deps"""
        self.client.deployments.update_labels('dep1', [{'label1': 'value1'}])
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1'],
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'label2': 'value2'}],
        )
        dep_id = group.deployment_ids[0]
        client_dep = self.client.deployments.get(dep_id)
        self.sm.get(models.Deployment, dep_id)
        self.assert_resource_labels(client_dep.labels, [
            {'label1': 'value1'}, {'label2': 'value2'}
        ])

    def test_add_labels_already_exist(self):
        labels = [{'label2': 'value2'}]
        self.client.deployments.update_labels('dep1', labels)
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1'],
        )
        self.client.deployment_groups.put(  # doesn't throw
            'group1',
            labels=labels,
        )
        dep = self.client.deployments.get('dep1')
        self.assert_resource_labels(dep.labels, labels)

    def test_add_labels_to_added_deployments(self):
        """Group labels are applied to deps added to the group"""
        labels = [{'label1': 'value1'}]
        self.client.deployment_groups.put(
            'group1',
            labels=labels,
        )
        self.client.deployment_groups.put(
            'group2',
            deployment_ids=['dep1']
        )
        filter_labels = [{'label': 'filter'}]
        self.client.deployments.update_labels('dep2', filter_labels)
        self.client.deployments_filters.create('filter1', [
            {'key': 'label', 'values': ['filter'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployments.create('blueprint', 'dep3')
        self.client.deployment_groups.put(
            'group1',
            # add a deployment using all 3 ways: by id, by clone, by filter
            deployments_from_group=['group2'],  # dep1
            filter_id='filter1',  # dep2
            deployment_ids=['dep3'],
        )
        dep1 = self.client.deployments.get('dep1')
        self.assert_resource_labels(dep1.labels, labels)
        dep2 = self.client.deployments.get('dep2')
        self.assert_resource_labels(dep2.labels, labels + filter_labels)
        dep3 = self.client.deployments.get('dep3')
        self.assert_resource_labels(dep3.labels, labels)

    def test_add_labels_deployments_added_twice(self):
        """Add a deployment twice, in two ways, to a group with labels.

        Only adds the labels once to the deployment.
        """
        labels = [{'label1': 'value1'}]
        self.client.deployment_groups.put(
            'group1',
            labels=labels,
        )
        self.client.deployment_groups.put(
            'group2',
            deployment_ids=['dep1']
        )
        self.client.deployment_groups.put(
            'group1',
            deployments_from_group=['group2'],  # dep1
            deployment_ids=['dep1'],
        )
        dep1 = self.client.deployments.get('dep1')
        self.assert_resource_labels(dep1.labels, labels)

    def test_add_invalid_label_parent(self):
        error_message = 'using label `csys-obj-parent` that does not exist'
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-obj-parent': 'value2'}],
            )
        group = self.client.deployment_groups.get('group1')
        dep1 = self.client.deployments.get('dep1')
        dep2 = self.client.deployments.get('dep2')
        self.assertEqual(len(group.labels), 0)
        self.assertEqual(len(dep1.labels), 0)
        self.assertEqual(len(dep2.labels), 0)

    def test_add_cyclic_parent_labels_in_group(self):
        error_message = 'results in cyclic deployment-labels dependencies'
        self.client.deployments.update_labels(
            'dep2', [{'csys-obj-parent': 'dep1'}])
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )

        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-obj-parent': 'dep2'}],
            )
        group = self.client.deployment_groups.get('group1')
        dep1 = self.client.deployments.get('dep1')
        dep2 = self.client.deployments.get('dep2')
        self.assertEqual(len(group.labels), 0)
        self.assertEqual(len(dep1.labels), 0)
        self.assertEqual(len(dep2.labels), 1)

    def test_add_self_deployment_as_parent(self):
        error_message = 'results in cyclic deployment-labels dependencies'
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )

        with self.assertRaisesRegex(CloudifyClientError, error_message):
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-obj-parent': 'dep1'}],
            )
        group = self.client.deployment_groups.get('group1')
        dep1 = self.client.deployments.get('dep1')
        self.assertEqual(len(group.labels), 0)
        self.assertEqual(len(dep1.labels), 0)

    def test_add_single_parent(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )

        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_services_count, 2)

    def test_add_multiple_parents(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )

        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.put_deployment(deployment_id='parent_2', blueprint_id='parent_2')

        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-parent': 'parent_2'}],
        )
        dep1 = self.client.deployments.get('parent_1')
        dep2 = self.client.deployments.get('parent_2')
        self.assertEqual(dep1.sub_services_count, 2)
        self.assertEqual(dep2.sub_services_count, 2)

    def test_add_parents_before_adding_deployment(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.put_deployment(deployment_id='parent_2', blueprint_id='parent_2')
        self.client.deployment_groups.put('group1')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-parent': 'parent_2'}],
        )
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        dep1 = self.client.deployments.get('parent_1')
        dep2 = self.client.deployments.get('parent_2')
        self.assertEqual(dep1.sub_services_count, 2)
        self.assertEqual(dep2.sub_services_count, 2)

    def test_add_parents_before_adding_deployments_from_groups(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.put_deployment(deployment_id='parent_2', blueprint_id='parent_2')
        self.put_deployment(deployment_id='parent_3', blueprint_id='parent_3')
        self.put_deployment(deployment_id='group2_1', blueprint_id='group2_1')

        self.client.deployment_groups.put('group1')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-parent': 'parent_2'},
                    {'csys-obj-parent': 'parent_3'}],
        )

        self.client.deployment_groups.put('group2', blueprint_id='blueprint')
        self.client.deployment_groups.put('group3', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group2',
            count=4
        )
        self.client.deployment_groups.add_deployments(
            'group3',
            deployment_ids=['dep1', 'dep2']
        )
        self.client.deployment_groups.add_deployments(
            'group1',
            deployments_from_group='group2'
        )
        self.client.deployment_groups.add_deployments(
            'group1',
            deployments_from_group='group3'
        )

        dep1 = self.client.deployments.get('parent_1')
        dep2 = self.client.deployments.get('parent_2')
        dep3 = self.client.deployments.get('parent_3')
        self.assertEqual(dep1.sub_services_count, 6)
        self.assertEqual(dep2.sub_services_count, 6)
        self.assertEqual(dep3.sub_services_count, 6)

    def test_add_parents_to_multiple_source_of_deployments(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.put_deployment(deployment_id='dep3', blueprint_id='dep3')
        self.put_deployment(deployment_id='dep4', blueprint_id='dep4')
        self.put_deployment(deployment_id='dep5', blueprint_id='dep5')

        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.put('group2', blueprint_id='blueprint')

        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        self.client.deployment_groups.add_deployments(
            'group2',
            deployment_ids=['dep1', 'dep2']
        )
        self.client.deployments.update_labels('dep3', [
            {'label1': 'value1'}
        ])
        self.client.deployments.update_labels('dep4', [
            {'label1': 'value1'}
        ])
        self.client.deployments_filters.create('filter1', [
            {'key': 'label1', 'values': ['value1'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployment_groups.put(
            'group1',
            filter_id='filter1',
            deployment_ids=['dep5'],
            deployments_from_group='group2'
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_services_count, 5)

    def test_add_parents_to_environment_deployments(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')

        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group1',
            count=4
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-type': 'environment'}],
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_environments_count, 4)

    def test_convert_service_to_environment_for_deployments(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group1',
            count=4
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_services_count, 4)
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-type': 'environment'}],
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_environments_count, 4)

    def test_convert_environment_to_service_for_deployments(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group1',
            count=4
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-type': 'environment'}],
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_environments_count, 4)
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_services_count, 4)

    def test_delete_parents_labels_from_deployments(self):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
            blueprint_id='blueprint'
        )
        self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_services_count, 2)
        self.client.deployment_groups.put(
            'group1',
            labels=[],
            blueprint_id='blueprint'
        )
        dep = self.client.deployments.get('parent_1')
        self.assertEqual(dep.sub_services_count, 0)

    @mock.patch(
        'manager_rest.rest.rest_utils.RecursiveDeploymentLabelsDependencies'
        '.propagate_deployment_statuses')
    def test_validate_update_deployment_statuses_after_conversion(self,
                                                                  mock_status):
        self.put_deployment(deployment_id='parent_1', blueprint_id='parent_1')
        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group1',
            count=4
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-type': 'environment'}],
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        mock_status.assert_called()


@mock.patch(
    'manager_rest.rest.resources_v3_1.executions.workflow_sendhandler',
    mock.Mock()
)
class ExecutionGroupsTestCase(base_test.BaseServerTestCase):
    def setUp(self):
        super(ExecutionGroupsTestCase, self).setUp()
        self.put_blueprint()
        dep = self.client.deployments.create('blueprint', 'dep1')
        self.create_deployment_environment(dep, None)
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1'],
            blueprint_id='blueprint',
        )

    def test_get_empty(self):
        result = self.client.execution_groups.list()
        assert len(result) == 0

    def test_create_from_group(self):
        group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install'
        )
        assert len(group.execution_ids) == 1
        execution = self.client.executions.get(group.execution_ids[0])
        assert execution.workflow_id == 'install'
        assert execution.deployment_id == 'dep1'

    def test_get_events(self):
        """Get events by group id.

        Include events for execution group, but not events for the particular
        executions (either in group or not).
        """
        group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install'
        )
        non_group_execution = self.client.executions.start(
            deployment_id='dep1',
            workflow_id='install',
            force=True,  # force, because there's one already running
        )
        # refetch as ORM objects so we can pass them to Log/Event
        execution_group = self.sm.get(models.ExecutionGroup, group.id)
        group_execution = self.sm.get(models.Execution, group.execution_ids[0])
        non_group_execution = self.sm.get(
            models.Execution, non_group_execution.id
        )
        self.sm.put(
            models.Log(
                message='log1',
                execution_group=execution_group,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Event(
                message='event1',
                execution_group=execution_group,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Log(
                message='log2',
                execution=group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Event(
                message='event2',
                execution=group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Log(
                message='log3',
                execution=non_group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Event(
                message='event3',
                execution=non_group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        events = self.client.events.list(
            execution_group_id=group['id'],
            include_logs=True
        )
        assert len(events) == 2
        assert all(e['execution_group_id'] == execution_group.id
                   for e in events)

    def test_one_fk_not_null_constraint(self):
        group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install'
        )
        # refetch as ORM objects so we can pass them to Log/Event
        execution_group = self.sm.get(models.ExecutionGroup, group.id)
        execution = self.sm.get(models.Execution, group.execution_ids[0])

        with self.assertRaisesRegex(SQLStorageException,
                                    'violates check constraint'):
            self.sm.put(
                models.Event(
                    message='event',
                    execution=execution,
                    execution_group=execution_group,
                    reported_timestamp=datetime.utcnow()
                )
            )
        with self.assertRaisesRegex(SQLStorageException,
                                    'violates check constraint'):
            self.sm.put(
                models.Event(
                    message='event',
                    reported_timestamp=datetime.utcnow()
                )
            )
        with self.assertRaisesRegex(SQLStorageException,
                                    'violates check constraint'):
            self.sm.put(
                models.Log(
                    message='log',
                    execution=execution,
                    execution_group=execution_group,
                    reported_timestamp=datetime.utcnow()
                )
            )
        with self.assertRaisesRegex(SQLStorageException,
                                    'violates check constraint'):
            self.sm.put(
                models.Log(
                    message='log',
                    reported_timestamp=datetime.utcnow()
                )
            )

    def test_get_execution_by_group(self):
        execution_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install'
        )
        self.client.executions.start(
            deployment_id='dep1',
            workflow_id='install',
            force=True,  # force, because there's one already running
        )
        executions = self.client.executions.list(
            _group_id=execution_group['id'])
        assert len(executions) == 1

    def test_get_execution_group(self):
        group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install'
        )
        execution = self.sm.get(models.Execution, group.execution_ids[0])
        execution.status = ExecutionState.TERMINATED
        self.sm.update(execution)
        retrieved = self.client.execution_groups.get(group.id)
        assert retrieved.id == group.id
        assert len(retrieved.execution_ids) == 1
        assert retrieved.status == ExecutionState.TERMINATED

        listed = self.client.execution_groups.list()[0]
        assert listed.id == group.id
        assert listed.get('status') is None
        assert listed.get('execution_ids') is None

    def test_delete_deployment(self):
        """It's still possible to delete a deployment used in an exec-group"""
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install'
        )
        with self.assertRaisesRegex(CloudifyClientError, 'running or queued'):
            self.client.deployments.delete('dep1')

        group_execs = self.sm.get(
            models.ExecutionGroup, exc_group.id).executions
        for exc in group_execs:
            exc.status = ExecutionState.TERMINATED
            self.sm.update(exc)

        self.client.deployments.delete('dep1')

        delete_exec = self.sm.get(models.Execution, None, filters={
            'workflow_id': 'delete_deployment_environment',
            'deployment_id': 'dep1'
        })
        # set the execution to started, so that we can update its status
        # via the restclient to terminated, which actually deletes
        # the deployment from the db
        delete_exec.status = ExecutionState.STARTED
        self.sm.update(delete_exec)
        self.client.executions.update(
            delete_exec.id, ExecutionState.TERMINATED)

        deps = self.client.deployments.list()
        assert len(deps) == 0

    def test_queues_over_concurrency(self):
        dep_ids = []
        for ix in range(5):
            dep_id = f'd{ix}'
            dep = self.client.deployments.create('blueprint', dep_id)
            self.create_deployment_environment(dep, None)
            dep_ids.append(dep_id)
        self.client.deployment_groups.put('group2', deployment_ids=dep_ids)
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group2',
            workflow_id='install',
            concurrency=3,
        )
        group_execs = self.sm.get(
            models.ExecutionGroup, exc_group.id).executions
        pending_execs = sum(
            exc.status == ExecutionState.PENDING for exc in group_execs)
        queued_execs = sum(
            exc.status == ExecutionState.QUEUED for exc in group_execs)
        assert pending_execs == exc_group.concurrency
        assert queued_execs == len(group_execs) - exc_group.concurrency

    @mock.patch('manager_rest.workflow_executor.execute_workflow', mock.Mock())
    @mock.patch('manager_rest.resource_manager.send_event', mock.Mock())
    def test_cancel_group(self):
        self.client.deployment_groups.add_deployments(
            'group1',
            count=2
        )
        for dep in self.client.deployments.list():
            if dep.id != 'dep1':
                self.create_deployment_environment(dep)
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        self.client.execution_groups.cancel(exc_group.id)
        group = self.sm.get(models.ExecutionGroup, exc_group.id)

        for exc in group.executions:
            assert exc.status in (
                ExecutionState.CANCELLED, ExecutionState.CANCELLING
            )

    @mock.patch('manager_rest.workflow_executor.execute_workflow', mock.Mock())
    @mock.patch('manager_rest.resource_manager.send_event', mock.Mock())
    def test_resume_group(self):
        """After all executions have been cancelled, resume them"""
        self.client.deployment_groups.add_deployments(
            'group1',
            count=2
        )
        for dep in self.client.deployments.list():
            if dep.id != 'dep1':
                self.create_deployment_environment(dep)
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        group = self.sm.get(models.ExecutionGroup, exc_group.id)

        for exc in group.executions:
            exc.status = ExecutionState.CANCELLED
            self.sm.update(exc)

        self.client.execution_groups.resume(exc_group.id)

        group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in group.executions:
            assert exc.status in (
                ExecutionState.PENDING, ExecutionState.QUEUED
            )

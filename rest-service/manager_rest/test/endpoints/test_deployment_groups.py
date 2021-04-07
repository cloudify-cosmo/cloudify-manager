import mock

from datetime import datetime

from cloudify.models_states import VisibilityState, ExecutionState
from cloudify_rest_client.exceptions import CloudifyClientError

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

        Include events for execution in the group, but not events for
        executions not in the group.
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
        group_execution = self.sm.get(models.Execution, group.execution_ids[0])
        non_group_execution = self.sm.get(
            models.Execution, non_group_execution.id
        )
        self.sm.put(
            models.Log(
                id='log1',
                message='log1',
                execution=group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Event(
                id='event1',
                message='event1',
                execution=group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Log(
                id='log2',
                message='log2',
                execution=non_group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        self.sm.put(
            models.Event(
                id='event2',
                message='event2',
                execution=non_group_execution,
                reported_timestamp=datetime.utcnow()
            )
        )
        events = self.client.events.list(
            execution_group_id=group['id'],
            include_logs=True
        )
        assert len(events) == 2
        assert all(e['execution_id'] == group_execution.id for e in events)

    def test_get_events_both_arguments(self):
        with self.assertRaisesRegex(CloudifyClientError, 'not both'):
            self.client.events.list(
                execution_group_id='group1', execution_id='exec1'
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

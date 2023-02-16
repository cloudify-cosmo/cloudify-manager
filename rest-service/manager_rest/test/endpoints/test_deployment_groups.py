import pytest
import unittest
from typing import Dict, Any
from unittest import mock

from datetime import datetime

from cloudify.models_states import VisibilityState, ExecutionState
from cloudify_rest_client.exceptions import (
    CloudifyClientError,
    IllegalExecutionParametersError,
)

from manager_rest.manager_exceptions import SQLStorageException, ConflictError
from manager_rest.storage import models, db
from manager_rest.rest.resources_v3_1.deployments import DeploymentGroupsId
from manager_rest import config

from manager_rest.test import base_test


class DeploymentGroupsTestCase(base_test.BaseServerTestCase):
    def setUp(self):
        super(DeploymentGroupsTestCase, self).setUp()
        self.blueprint = models.Blueprint(
            id='blueprint',
            creator=self.user,
            tenant=self.tenant,
            plan={'inputs': {}},
            state='uploaded',
        )
        for dep_id in ['dep1', 'dep2']:
            db.session.add(models.Deployment(
                id=dep_id,
                creator=self.user,
                display_name='',
                tenant=self.tenant,
                blueprint=self.blueprint,
                workflows={'install': {'operation': ''}}
            ))

    def _deployment(self, **kwargs):
        dep_params = {
            'creator': self.user,
            'tenant': self.tenant,
            'blueprint': self.blueprint
        }
        dep_params.update(kwargs)
        dep = models.Deployment(**dep_params)
        db.session.add(dep)
        return dep

    def test_dep_group_include_joinedload(self):
        # RD-5363 Make sure we don't choke on joinedload again
        self.client.deployment_groups.list(
            _include=['deployment_ids', 'labels'],
        )

    def test_get_empty(self):
        result = self.client.deployment_groups.list()
        assert len(result) == 0

    def test_add_empty_group(self):
        result = self.client.deployment_groups.list()
        assert len(result) == 0
        result = self.client.deployment_groups.put('group1')
        assert result['id'] == 'group1'
        assert len(self.client.deployment_groups.list()) == 1

    def test_add_to_group(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        assert set(group.deployment_ids) == {'dep1', 'dep2'}

    def test_overwrite_group(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']

    def test_clear_group(self):
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']

        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=[]
        )
        assert group.deployment_ids == []

    def test_update_attributes(self):
        """When deployment_ids is not provided, the group is not cleared"""
        group = self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )
        assert group.deployment_ids == ['dep1']
        assert not group.description
        assert not group.default_blueprint_id
        assert not group.default_inputs
        group = self.client.deployment_groups.put(
            'group1',
            description='descr',
            blueprint_id='blueprint',
            default_inputs={'inp1': 'value'}
        )
        assert group.description == 'descr'
        assert group.deployment_ids == ['dep1']
        assert group.default_blueprint_id == 'blueprint'
        assert group.default_inputs == {'inp1': 'value'}
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.deployment_groups.put(
                'group1',
                blueprint_id='nonexistent',
            )
        assert cm.exception.status_code == 404

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
        assert dep.id.startswith('group1-')

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
        assert len(group.deployment_ids) == 2
        group = self.client.deployment_groups.put(
            'group1',
            new_deployments=[{}]
        )
        assert 'dep1' in group.deployment_ids
        assert len(group.deployment_ids) == 3

    def test_create_from_spec(self):
        self.blueprint.plan['inputs'] = {'http_web_server_port': {}}
        inputs = {'http_web_server_port': 1234}
        labels = [{'label1': 'label-value'}]
        group = self.client.deployment_groups.put(
            'group1',
            blueprint_id='blueprint',
            new_deployments=[
                {
                    'id': 'spec_dep1',
                    'inputs': inputs,
                    'labels': labels,
                }
            ]
        )

        assert set(group.deployment_ids) == {'spec_dep1'}
        sm_group = self.sm.get(models.DeploymentGroup, 'group1')
        assert sm_group.creation_counter == 1
        deps = sm_group.deployments
        assert len(deps) == 1
        create_exec_params = deps[0].create_execution.parameters
        assert create_exec_params['inputs'] == inputs
        assert create_exec_params['labels'] == [
            {'key': 'label1', 'value': 'label-value',
             'created_at': None, 'created_by': None}
        ]

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

    def test_add_nonexistent(self):
        self.client.deployment_groups.put('group1')
        with self.assertRaisesRegex(CloudifyClientError, 'not found') as cm:
            self.client.deployment_groups.add_deployments(
                'group1',
                deployment_ids=['nonexistent']
            )
        assert cm.exception.status_code == 404
        with self.assertRaisesRegex(CloudifyClientError, 'not found') as cm:
            self.client.deployment_groups.add_deployments(
                'group1',
                filter_id='nonexistent'
            )
        assert cm.exception.status_code == 404

    def test_remove_nonexistent(self):
        self.client.deployment_groups.put('group1')
        with self.assertRaisesRegex(CloudifyClientError, 'not found') as cm:
            self.client.deployment_groups.remove_deployments(
                'group1',
                deployment_ids=['nonexistent']
            )
        assert cm.exception.status_code == 404
        with self.assertRaisesRegex(CloudifyClientError, 'not found') as cm:
            self.client.deployment_groups.remove_deployments(
                'group1',
                filter_id='nonexistent'
            )
        assert cm.exception.status_code == 404

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

        # dep hasn't been deleted _yet_, but check that delete-dep-env for it
        # was run
        dep = self.sm.get(models.Deployment, 'dep1')
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

    def test_add_from_filter_ids(self):
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

    def test_add_from_filter_rules(self):
        """Extend a group providing filter_rules"""
        self.client.deployments.update_labels('dep1', [
            {'label1': 'value1'}
        ])
        self.client.deployment_groups.put('group1')
        self.client.deployment_groups.add_deployments(
            'group1',
            filter_rules=[{'key': 'label1',
                           'values': ['value1'],
                           'operator': 'any_of',
                           'type': 'label'}]
        )
        group = self.client.deployment_groups.get('group1')
        assert group.deployment_ids == ['dep1']

    def test_add_from_filters(self):
        """Extend a group providing filter_id and filter_rules"""
        self.client.deployments.update_labels('dep1', [
            {'label1': 'value1'}
        ])
        self.client.deployments.update_labels('dep2', [
            {'label1': 'value2'}
        ])
        self.client.deployments_filters.create('filter1', [
            {'key': 'label1', 'values': ['value1'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployment_groups.put('group1')
        self.client.deployment_groups.add_deployments(
            'group1',
            filter_id='filter1',
            filter_rules=[{'key': 'label1',
                           'values': ['value2'],
                           'operator': 'any_of',
                           'type': 'label'}]
        )
        group = self.client.deployment_groups.get('group1')
        assert set(group.deployment_ids) == {'dep2', 'dep1'}

    def test_remove_from_filters(self):
        """Shrink a group providing filter_id and filter_rules"""
        self.client.deployments.update_labels('dep1', [
            {'label1': 'value1'}
        ])
        self.client.deployments.update_labels('dep2', [
            {'label1': 'value2'}
        ])
        self.client.deployments_filters.create('filter1', [
            {'key': 'label1', 'values': ['value1'],
             'operator': 'any_of', 'type': 'label'}
        ])
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        self.client.deployment_groups.remove_deployments(
            'group1',
            filter_id='filter1',
            filter_rules=[{'key': 'label1',
                           'values': ['value2'],
                           'operator': 'any_of',
                           'type': 'label'}]
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
        self.client.deployment_groups.put('group3')  # empty group
        group1 = self.client.deployment_groups.remove_deployments(
            'group1',
            deployments_from_group='group3'
        )
        assert set(group1.deployment_ids) == {'dep1', 'dep2'}
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
        assert set((label['key'], label['value'])
                   for label in dep.create_execution.parameters['labels']) == {
            # from new_deployments:
            ('label1', 'value1'),
            ('label1', 'value2'),
            ('label3', 'value4'),
            # from the group:
            # ('label1', 'value1') - not present - deduplicated
            ('label2', 'value2')

        }

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
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-invalid': 'xxx'}],
            )
        assert cm.exception.status_code == 400
        with self.assertRaises(CloudifyClientError) as cm:
            self.client.deployment_groups.put(
                'group1',
                labels=[{'łó-disallowed-characters': 'xxx'}],
            )
        assert cm.exception.status_code == 400
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
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        with self.assertRaisesRegex(CloudifyClientError, 'not found'):
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-obj-parent': 'value2'}],
            )
        group = self.client.deployment_groups.get('group1')
        dep1 = self.client.deployments.get('dep1')
        dep2 = self.client.deployments.get('dep2')
        assert len(group.labels) == 0
        assert len(dep1.labels) == 0
        assert len(dep2.labels) == 0

    def test_add_cyclic_parent_labels_in_group(self):
        self.client.deployments.update_labels(
            'dep2', [{'csys-obj-parent': 'dep1'}])
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )

        with self.assertRaisesRegex(CloudifyClientError, 'cyclic'):
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-obj-parent': 'dep2'}],
            )
        group = self.client.deployment_groups.get('group1')
        dep1 = self.client.deployments.get('dep1')
        dep2 = self.client.deployments.get('dep2')

        # Defining dep1 as a parent will add a consumer label to it
        sanitized_dep1_labels = \
            [lb for lb in dep1.labels if lb.key != 'csys-consumer-id']

        assert len(group.labels) == 0
        assert len(sanitized_dep1_labels) == 0
        assert len(dep2.labels) == 1

    def test_add_self_deployment_as_parent(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1']
        )

        with self.assertRaisesRegex(CloudifyClientError, 'cyclic'):
            self.client.deployment_groups.put(
                'group1',
                labels=[{'csys-obj-parent': 'dep1'}],
            )
        group = self.client.deployment_groups.get('group1')
        dep1 = self.client.deployments.get('dep1')
        assert len(group.labels) == 0
        assert len(dep1.labels) == 0

    def test_add_single_parent(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )

        parent = self._deployment(id='parent_1')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        assert parent.sub_services_count == 2

    def test_add_multiple_parents(self):
        self.client.deployment_groups.put(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )

        parent1 = self._deployment(id='parent_1')
        parent2 = self._deployment(id='parent_2')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-parent': 'parent_2'}],
        )
        assert parent1.sub_services_count == 2
        assert parent2.sub_services_count == 2

    def test_add_parents_before_adding_deployment(self):
        parent1 = self._deployment(id='parent_1')
        parent2 = self._deployment(id='parent_2')
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
        assert parent1.sub_services_count == 2
        assert parent2.sub_services_count == 2

    def test_add_parents_before_adding_deployments_from_groups(self):
        parent1 = self._deployment(id='parent_1')
        parent2 = self._deployment(id='parent_2')
        parent3 = self._deployment(id='parent_3')

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
        assert parent1.sub_services_count == 6
        assert parent2.sub_services_count == 6
        assert parent3.sub_services_count == 6

    def test_add_parents_to_multiple_source_of_deployments(self):
        parent1 = self._deployment(id='parent_1')
        self._deployment(id='dep3')
        self._deployment(id='dep4')
        self._deployment(id='dep5')

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
        assert parent1.sub_services_count == 5

    def test_add_parents_to_environment_deployments(self):
        parent1 = self._deployment(id='parent_1')

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
        assert parent1.sub_environments_count == 4

    def test_convert_service_to_environment_for_deployments(self):
        parent1 = self._deployment(id='parent_1')
        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group1',
            count=4
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        assert parent1.sub_services_count == 4
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-type': 'environment'}],
        )
        assert parent1.sub_environments_count == 4

    def test_convert_environment_to_service_for_deployments(self):
        parent1 = self._deployment(id='parent_1')
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
        assert parent1.sub_environments_count == 4
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
        )
        assert parent1.sub_services_count == 4

    def test_delete_parents_labels_from_deployments(self):
        parent1 = self._deployment(id='parent_1')
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'}],
            blueprint_id='blueprint'
        )
        self.client.deployment_groups.add_deployments(
            'group1',
            deployment_ids=['dep1', 'dep2']
        )
        assert parent1.sub_services_count == 2
        self.client.deployment_groups.put(
            'group1',
            labels=[],
            blueprint_id='blueprint'
        )
        assert parent1.sub_services_count == 0

    def test_validate_update_deployment_statuses_after_conversion(self):
        parent1 = self._deployment(id='parent_1')
        self.client.deployment_groups.put('group1', blueprint_id='blueprint')
        self.client.deployment_groups.add_deployments(
            'group1',
            count=1
        )
        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-parent': 'parent_1'},
                    {'csys-obj-type': 'environment'}],
        )
        group_deployment = self.sm.get(
            models.DeploymentGroup, 'group1').deployments[0]
        assert parent1.sub_environments_count == 1
        assert parent1.sub_services_count == 0
        assert parent1.sub_services_status is None
        assert parent1.sub_environments_status \
            == group_deployment.deployment_status

        self.client.deployment_groups.put(
            'group1',
            labels=[{'csys-obj-type': 'service'},
                    {'csys-obj-parent': 'parent_1'}],
        )

        assert parent1.sub_environments_count == 0
        assert parent1.sub_services_count == 1
        assert parent1.sub_environments_status is None
        assert parent1.sub_services_status \
            == group_deployment.deployment_status

    def test_invalid_inputs(self):
        self.blueprint.plan['inputs'] = {'http_web_server_port': {}}
        self.client.deployment_groups.put(
                'group1',
                blueprint_id='blueprint',
                new_deployments=[
                    {'inputs': {'http_web_server_port': 8080}}
                ])
        with self.assertRaisesRegex(CloudifyClientError, 'unknown input'):
            self.client.deployment_groups.put(
                'group1',
                new_deployments=[
                    {'inputs': {
                        'nonexistent': 42,
                        'http_web_server_port': 8080,
                    }}
                ])


class ExecutionGroupsTestCase(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
            plan={'inputs': {}},
        )
        self.deployment = models.Deployment(
            id='dep1',
            creator=self.user,
            display_name='',
            tenant=self.tenant,
            blueprint=bp,
            workflows={'install': {'operation': ''}}
        )
        self.dep_group = models.DeploymentGroup(
            id='group1',
            default_blueprint=bp,
            tenant=self.tenant,
            creator=self.user,
        )
        self.dep_group.deployments.append(self.deployment)
        db.session.add(self.deployment)

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

    def test_list_groups_count(self):
        group1 = models.ExecutionGroup(
            id='group1',
            workflow_id='workflow',
            creator=self.user,
            tenant=self.tenant,
        )
        group2 = models.ExecutionGroup(
            id='group2',
            workflow_id='workflow',
            creator=self.user,
            tenant=self.tenant,
        )
        group3 = models.ExecutionGroup(
            id='group3',
            workflow_id='workflow',
            creator=self.user,
            tenant=self.tenant,
        )
        group1.executions = [
            models.Execution(
                id='exc1',
                workflow_id='workflow',
                creator=self.user,
                tenant=self.tenant,
            ),
            models.Execution(
                id='exc2',
                workflow_id='workflow',
                creator=self.user,
                tenant=self.tenant,
            ),
        ]
        group2.executions = [
            models.Execution(
                id=f'exc_group2_{i}',
                workflow_id='workflow',
                creator=self.user,
                tenant=self.tenant,
            ) for i in range(6)
        ]
        group3.executions = [
            models.Execution(
                id='trailing',
                workflow_id='workflow',
                creator=self.user,
                tenant=self.tenant,
            ),
        ]

        orig_page_size = config.instance.default_page_size
        config.instance.default_page_size = 3

        def fix_page_size():
            config.instance.default_page_size = orig_page_size

        groups = self.client.execution_groups.list(
            _include=['id', 'execution_ids'],
            _get_data=True,
        )
        # before RD-5334, this used to return 4 (because there's 4 executions)
        assert groups.metadata.pagination.total == 3
        assert groups.metadata.pagination.size == 3
        assert len(groups) == 3
        assert {group.id: set(group.execution_ids) for group in groups} == {
            'group1': {'exc1', 'exc2'},
            'group2': {f'exc_group2_{i}' for i in range(6)},
            'group3': {'trailing'},
        }

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
        models.ExecutionGroup(
            id='gr1',
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
        )
        exc1 = models.Execution(
            id='gr1',
            workflow_id='install',
            deployment=self.deployment,
            status=ExecutionState.QUEUED,
            tenant=self.tenant,
            creator=self.user,
        )
        with self.assertRaisesRegex(CloudifyClientError, 'running or queued'):
            self.client.deployments.delete('dep1')

        exc1.status = ExecutionState.TERMINATED
        self.client.deployments.delete('dep1')

        delete_exec = self.sm.get(models.Execution, None, filters={
            'workflow_id': 'delete_deployment_environment',
            'deployment_id': 'dep1'
        })
        # set the execution to started, so that we can update its status
        # via the restclient to terminated, which actually deletes
        # the deployment from the db
        delete_exec.status = ExecutionState.STARTED
        self.client.executions.update(
            delete_exec.id, ExecutionState.TERMINATED)

        assert db.session.query(models.Deployment).count() == 0

    def test_queues_over_concurrency(self):
        exc_group = models.ExecutionGroup(
            id='gr1',
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
        )
        for _ in range(5):
            exc_group.executions.append(models.Execution(
                workflow_id='create_deployment_environment',
                tenant=self.tenant,
                creator=self.user,
                status=ExecutionState.PENDING,
                parameters={}
            ))
        exc_group.concurrency = 3
        messages = exc_group.start_executions(self.sm, self.rm)
        assert len(messages) == exc_group.concurrency
        assert sum(exc.status == ExecutionState.PENDING
                   for exc in exc_group.executions) == exc_group.concurrency
        assert sum(exc.status == ExecutionState.QUEUED
                   for exc in exc_group.executions) == 2

    def test_doesnt_start_finished(self):
        exc_group = models.ExecutionGroup(
            id='gr1',
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
        )
        for exc_status in [ExecutionState.FAILED, ExecutionState.TERMINATED]:
            exc_group.executions.append(models.Execution(
                workflow_id='create_deployment_environment',
                tenant=self.tenant,
                creator=self.user,
                status=exc_status,
            ))
        messages = exc_group.start_executions(self.sm, self.rm)
        assert len(messages) == 0

    def test_cancel_group(self):
        exc_group = models.ExecutionGroup(
            id='gr1',
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
        )
        ex1 = models.Execution(
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
            status=ExecutionState.STARTED,
        )
        ex2 = models.Execution(
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
            status=ExecutionState.STARTED,
        )
        exc_group.executions = [ex1, ex2]
        self.client.execution_groups.cancel(exc_group.id)

        for exc in exc_group.executions:
            assert exc.status in (
                ExecutionState.CANCELLED, ExecutionState.CANCELLING
            )

    @mock.patch('manager_rest.workflow_executor.execute_workflow')
    def test_resume_group(self, mock_execute):
        """After all executions have been cancelled, resume them"""
        exc_group = models.ExecutionGroup(
            id='gr1',
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
        )
        ex1 = models.Execution(
            workflow_id='create_deployment_environment',
            parameters={},
            tenant=self.tenant,
            creator=self.user,
            status=ExecutionState.CANCELLED,
        )
        ex2 = models.Execution(
            workflow_id='create_deployment_environment',
            parameters={},
            tenant=self.tenant,
            creator=self.user,
            status=ExecutionState.CANCELLED,
        )
        exc_group.executions = [ex1, ex2]
        self.client.execution_groups.resume(exc_group.id)

        group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in group.executions:
            assert exc.status in (
                ExecutionState.PENDING, ExecutionState.QUEUED
            )
        mock_execute.assert_called()

    def test_invalid_parameters(self):
        with self.assertRaises(IllegalExecutionParametersError):
            self.client.execution_groups.start(
                deployment_group_id='group1',
                workflow_id='install',
                parameters={
                    'dep1': {'invalid-input': 42}
                }
            )
        with self.assertRaises(IllegalExecutionParametersError):
            self.client.execution_groups.start(
                deployment_group_id='group1',
                workflow_id='install',
                default_parameters={'invalid-input': 42}
            )

    def test_group_status(self):
        for execution_statuses, expected_group_status in [
            ([], None),
            ([ExecutionState.PENDING], ExecutionState.PENDING),
            ([ExecutionState.QUEUED], ExecutionState.QUEUED),
            ([ExecutionState.TERMINATED], ExecutionState.TERMINATED),
            ([ExecutionState.STARTED], ExecutionState.STARTED),
            ([ExecutionState.FAILED], ExecutionState.FAILED),
            ([ExecutionState.TERMINATED, ExecutionState.FAILED],
             ExecutionState.FAILED),
            ([ExecutionState.STARTED, ExecutionState.PENDING,
              ExecutionState.TERMINATED],
             ExecutionState.STARTED),
            ([ExecutionState.TERMINATED, ExecutionState.STARTED],
             ExecutionState.STARTED)
        ]:
            with self.subTest():
                exc_group = models.ExecutionGroup(
                    id='gr1',
                    workflow_id='',
                    tenant=self.tenant,
                    creator=self.user,
                )
                for exc_status in execution_statuses:
                    exc = models.Execution(
                        workflow_id='',
                        tenant=self.tenant,
                        creator=self.user,
                        status=exc_status
                    )
                    exc_group.executions.append(exc)
                assert exc_group.status == expected_group_status

    @mock.patch('manager_rest.workflow_executor.execute_workflow', mock.Mock())
    def test_success_group(self):
        # executions are already terminated when we add success_group, so
        # they should be in the success group
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        sm_exc_group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in sm_exc_group.executions:
            exc.status = ExecutionState.TERMINATED
            self.sm.put(exc)
        self.client.deployment_groups.put('group2')
        self.client.execution_groups.set_target_group(
            exc_group.id, success_group='group2')
        target_group = self.sm.get(models.DeploymentGroup, 'group2')
        assert len(target_group.deployments) == 1

        # executions terminate after we add the success group
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        self.client.deployment_groups.put('group3')
        self.client.execution_groups.set_target_group(
            exc_group.id, success_group='group3')
        sm_exc_group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in sm_exc_group.executions:
            self.client.executions.update(
                exc.id, status=ExecutionState.TERMINATED)
        target_group = self.sm.get(models.DeploymentGroup, 'group3')
        assert len(target_group.deployments) == 1

        # same as above, but the deployment already is in the target group
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        self.client.deployment_groups.put('group3', deployment_ids=['dep1'])
        self.client.execution_groups.set_target_group(
            exc_group.id, success_group='group3')
        sm_exc_group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in sm_exc_group.executions:
            self.client.executions.update(
                exc.id, status=ExecutionState.TERMINATED)
        target_group = self.sm.get(models.DeploymentGroup, 'group3')
        assert len(target_group.deployments) == 1

    @mock.patch('manager_rest.workflow_executor.execute_workflow', mock.Mock())
    def test_failed_group(self):
        # similar to test_success_group, but for the failed group
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        sm_exc_group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in sm_exc_group.executions:
            exc.status = ExecutionState.FAILED
            self.sm.put(exc)
        self.client.deployment_groups.put('group2')
        self.client.execution_groups.set_target_group(
            exc_group.id, failed_group='group2')
        target_group = self.sm.get(models.DeploymentGroup, 'group2')
        assert len(target_group.deployments) == 1

        # executions terminate after we add the success group
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        self.client.deployment_groups.put('group3')
        self.client.execution_groups.set_target_group(
            exc_group.id, failed_group='group3')
        sm_exc_group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in sm_exc_group.executions:
            self.client.executions.update(
                exc.id, status=ExecutionState.FAILED)
        target_group = self.sm.get(models.DeploymentGroup, 'group3')
        assert len(target_group.deployments) == 1

        # same as above, but the deployment already is in the target group
        exc_group = self.client.execution_groups.start(
            deployment_group_id='group1',
            workflow_id='install',
        )
        self.client.deployment_groups.put('group3', deployment_ids=['dep1'])
        self.client.execution_groups.set_target_group(
            exc_group.id, failed_group='group3')
        sm_exc_group = self.sm.get(models.ExecutionGroup, exc_group.id)
        for exc in sm_exc_group.executions:
            self.client.executions.update(
                exc.id, status=ExecutionState.FAILED)
        target_group = self.sm.get(models.DeploymentGroup, 'group3')
        assert len(target_group.deployments) == 1

    def test_set_concurrency(self):
        exc_group = models.ExecutionGroup(
            id='excgroup1',
            workflow_id='install',
            deployment_group=self.dep_group,
            concurrency=10,
            creator=self.user,
            tenant=self.tenant,
        )
        self.client.execution_groups.set_concurrency(exc_group.id, 20)
        assert exc_group.concurrency == 20

    def test_set_invalid_concurrency(self):
        exc_group = models.ExecutionGroup(
            id='excgroup1',
            workflow_id='install',
            deployment_group=self.dep_group,
            concurrency=10,
            creator=self.user,
            tenant=self.tenant,
        )
        for try_concurrency in [-1, 'abcd', {}]:
            with self.assertRaises(CloudifyClientError) as cm:
                self.client.execution_groups.set_concurrency(
                    exc_group.id, try_concurrency)
            assert cm.exception.status_code == 400
        assert exc_group.concurrency == 10


class TestGenerateID(unittest.TestCase):
    def setUp(self):
        self.endpoint = DeploymentGroupsId()

    def _mock_blueprint(self, id_template=None):
        bp = mock.MagicMock()
        bp.id = 'blueprint_id'
        bp.plan = {
            'deployment_settings': {'id_template': id_template}
        }
        return bp

    def _generate_id(self, group, new_dep_spec):
        return self.endpoint._new_deployment_id(group, new_dep_spec)

    def test_from_blueprint(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint('hello-{uuid}')
        new_id, is_unique = self._generate_id(group, {})
        assert is_unique
        assert new_id.startswith('hello')
        assert len(new_id) > 36

    def test_from_blueprint_no_variable(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint('hello')
        with pytest.raises(ConflictError):
            self._generate_id(group, {})

    def test_group_id(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        new_id, is_unique = self._generate_id(group, {})
        assert is_unique
        assert new_id.startswith('g1')
        assert len(new_id) > 36

    def test_spec_no_variable(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        new_id, is_unique = self._generate_id(group, {'id': 'hello'})
        assert not is_unique
        assert new_id == 'hello'

    def test_spec_template(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        new_id, is_unique = self._generate_id(
            group, {'id': 'hello-{group_id}'})
        assert not is_unique
        assert new_id == 'hello-g1'

    def test_spec_uuid(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        new_id, is_unique = self._generate_id(group, {'id': 'hello-{uuid}'})
        assert is_unique
        assert new_id.startswith('hello')
        assert len(new_id) > 36

    def test_blueprint_id(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        new_id, _ = self._generate_id(
            group, {'id': '{blueprint_id}-{uuid}'})
        assert new_id.startswith(group.default_blueprint.id)

    def test_creation_counter(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        group.creation_counter = 42
        new_id, _ = self._generate_id(group, {'id': '{group_id}-{count}'})
        assert new_id == 'g1-42'

    def test_site_name(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        new_id, _ = self._generate_id(
            group, {'id': '{site_name}-{uuid}', 'site_name': 'a'})
        assert new_id.startswith('a-')

    def test_display_name(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        dep_spec = {'display_name': '{group_id}'}
        self._generate_id(group, dep_spec)
        assert dep_spec['display_name'] == 'g1'

    def test_display_name_same_uuid(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        dep_spec = {'id': '{group_id}-{uuid}',
                    'display_name': '{group_id}-{uuid}'}
        new_id, _ = self._generate_id(group, dep_spec)
        assert dep_spec['display_name'] == new_id

    def test_display_name_from_dsl(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        group.default_blueprint.plan['deployment_settings']['display_name'] =\
            'display-name-{uuid}'
        dep_spec: Dict[str, Any] = {}
        new_id, _ = self._generate_id(group, dep_spec)
        assert dep_spec['display_name'].startswith('display-name')
        assert len(dep_spec['display_name']) > 36

    def test_display_name_from_dsl_function(self):
        group = models.DeploymentGroup(id='g1')
        group.default_blueprint = self._mock_blueprint()
        group.default_blueprint.plan['deployment_settings']['display_name'] =\
            {'concat': ['display', 'name']}
        dep_spec: Dict[str, Any] = {}
        new_id, _ = self._generate_id(group, dep_spec)
        assert not dep_spec.get('display_name')

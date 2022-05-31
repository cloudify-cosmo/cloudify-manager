import uuid

from cloudify.models_states import DeploymentState
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.deployment_dependencies import create_deployment_dependency

from manager_rest.storage import db, models
from manager_rest.manager_exceptions import NotFoundError, ConflictError
from manager_rest.rest.rest_utils import update_inter_deployment_dependencies

from manager_rest.test.base_test import BaseServerTestCase


class _DependencyTestUtils(object):
    def setUp(self):
        super().setUp()
        self.bp1 = models.Blueprint(tenant=self.tenant, creator=self.user)

    def _deployment(self, **kwargs):
        dep_params = {
            'blueprint': self.bp1,
            'display_name': 'a',
            'creator': self.user,
            'tenant': self.tenant
        }
        dep_params.update(kwargs)
        dep = models.Deployment(**dep_params)
        db.session.add(dep)
        return dep

    def _dependency(self, source, target, **kwargs):
        idd_params = {
            'source_deployment': source,
            'target_deployment': target,
            'tenant': self.tenant,
            'dependency_creator': '',
            'creator': self.user,
        }
        idd_params.update(kwargs)
        idd = models.InterDeploymentDependencies(**idd_params)
        db.session.add(idd)
        return idd

    def _label_dependency(self, source, target):
        db.session.add(models.DeploymentLabelsDependencies(
            source_deployment=source,
            target_deployment=target,
            tenant=self.tenant,
            creator=self.user
        ))

    def _label(self, dep, k, v):
        db.session.add(models.DeploymentLabel(
            deployment=dep,
            creator=self.user,
            key=k,
            value=v
        ))


class ChildrenSummaryTest(_DependencyTestUtils, BaseServerTestCase):
    def test_empty(self):
        d1 = self._deployment(id='d1')
        summary = models.DeploymentLabelsDependencies.get_children_summary(d1)
        db.session.flush()
        assert summary.environments.count == 0
        assert summary.services.count == 0

    def test_service_dependency(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d1.deployment_status = DeploymentState.GOOD
        self._deployment(id='unrelated')
        self._label_dependency(d1, d2)
        db.session.flush()

        summary = models.DeploymentLabelsDependencies.get_children_summary(d2)
        assert summary.environments.count == 0
        assert summary.services.count == 1

    def test_multiple_services_status(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        d1.deployment_status = DeploymentState.GOOD
        d3.deployment_status = DeploymentState.REQUIRE_ATTENTION
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        db.session.flush()

        summary = models.DeploymentLabelsDependencies.get_children_summary(d2)
        assert set(summary.services.deployment_statuses) == {
            DeploymentState.GOOD, DeploymentState.REQUIRE_ATTENTION
        }

    def test_multiple_services_count(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        d1.sub_services_count = 1
        d3.sub_services_count = 2
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        db.session.flush()

        summary = models.DeploymentLabelsDependencies.get_children_summary(d2)
        assert summary.services.sub_services_total == 3

    def test_env_dependency(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._label(d1, 'csys-obj-type', 'environment')
        self._deployment(id='unrelated')
        self._label_dependency(d1, d2)
        db.session.flush()

        summary = models.DeploymentLabelsDependencies.get_children_summary(d2)
        assert summary.environments.count == 1
        assert summary.services.count == 0

    def test_multiple_envs_status(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._label(d1, 'csys-obj-type', 'environment')
        self._label(d3, 'csys-obj-type', 'environment')
        d1.deployment_status = DeploymentState.GOOD
        d3.deployment_status = DeploymentState.REQUIRE_ATTENTION
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        db.session.flush()

        summary = models.DeploymentLabelsDependencies.get_children_summary(d2)
        assert set(summary.environments.deployment_statuses) == {
            DeploymentState.GOOD, DeploymentState.REQUIRE_ATTENTION
        }

    def test_multiple_envs_total(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._label(d1, 'csys-obj-type', 'environment')
        self._label(d3, 'csys-obj-type', 'environment')
        d1.sub_environments_count = 1
        d3.sub_environments_count = 2
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        db.session.flush()

        summary = models.DeploymentLabelsDependencies.get_children_summary(d2)
        assert summary.environments.sub_environments_total == 3


class ModelDependenciesTest(_DependencyTestUtils, BaseServerTestCase):
    def test_empty(self):
        d1 = self._deployment(id='d1')
        db.session.flush()
        assert d1.get_dependencies() == []
        assert d1.get_dependents() == []
        assert d1.get_ancestors() == []
        assert d1.get_descendants() == []

    def test_direct_dependency(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._deployment(id='unrelated')
        self._dependency(d1, d2)
        db.session.flush()
        assert d1.get_dependencies() == [d2]
        assert d2.get_dependents() == [d1]

    def test_multiple_dependencies(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._dependency(d1, d2)
        self._dependency(d3, d2)
        db.session.flush()
        assert d1.get_dependencies() == d3.get_dependencies() == [d2]
        assert set(d2.get_dependents()) == {d1, d3}

    def test_multi_level(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._dependency(d1, d2)
        self._dependency(d2, d3)
        db.session.flush()
        assert set(d1.get_dependencies()) == {d2, d3}
        assert set(d3.get_dependents()) == {d1, d2}

        assert set(d2.get_dependents()) == {d1}
        assert set(d2.get_dependencies()) == {d3}

    def test_dependency_objects(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._deployment(id='unrelated')
        self._dependency(d1, d2)
        db.session.flush()
        deps = d1.get_dependencies(fetch_deployments=False)
        deps2 = d2.get_dependents(fetch_deployments=False)
        assert deps == deps2
        assert len(deps) == 1
        dep = deps[0]
        assert isinstance(dep, models.InterDeploymentDependencies)
        assert dep.source_deployment == d1
        assert dep.target_deployment == d2

    def test_label_dependencies(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._deployment(id='unrelated')
        self._label_dependency(d1, d2)
        db.session.flush()
        assert d1.get_dependencies() == []
        assert d2.get_dependents() == []
        assert d1.get_ancestors() == [d2]
        assert d2.get_descendants() == [d1]

    def test_label_dependencies_objects(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._label_dependency(d1, d2)
        db.session.flush()
        deps = d1.get_ancestors(fetch_deployments=False)
        deps2 = d2.get_descendants(fetch_deployments=False)
        assert deps == deps2
        assert len(deps) == 1
        dep = deps[0]
        assert isinstance(dep, models.DeploymentLabelsDependencies)
        assert dep.source_deployment == d1
        assert dep.target_deployment == d2

    def test_get_all(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        d4 = self._deployment(id='d4')
        self._deployment(id='unrelated')
        self._dependency(d1, d2)
        self._label_dependency(d3, d2)
        self._dependency(d3, d4)
        db.session.flush()
        assert d1.get_all_dependents() == set()
        assert d3.get_all_dependents() == set()

        assert d2.get_all_dependencies() == set()
        assert d4.get_all_dependencies() == set()

        assert d1.get_all_dependencies() == {d2}
        assert d3.get_all_dependencies() == {d2, d4}

        assert d2.get_all_dependents() == {d1, d3}
        assert d4.get_all_dependents() == {d3}

    def test_list_deployments_dependencies_filter(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        d4 = self._deployment(id='d4')
        self._dependency(d1, d2)
        self._dependency(d1, d4)
        self._dependency(d2, d3)
        assert {'d2', 'd3', 'd4'} ==\
            {d.id for d in self.client.deployments.list(_dependencies_of='d1')}
        assert {'d3'} ==\
            {d.id for d in self.client.deployments.list(_dependencies_of='d2')}
        assert set() ==\
            {d.id for d in self.client.deployments.list(_dependencies_of='d3')}


class RecalcAncestorsTest(_DependencyTestUtils, BaseServerTestCase):
    def test_no_relation(self):
        d1 = self._deployment(id='d1')
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d1)
        assert d1.sub_services_count == 0
        assert d1.sub_environments_count == 0

    def test_direct_dependency(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._deployment(id='unrelated')
        self._label_dependency(d1, d2)
        d1.deployment_status = DeploymentState.GOOD
        db.session.flush()
        assert d2.sub_services_count == 0
        assert d2.sub_services_status is None
        assert d2.deployment_status is None
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        assert d2.sub_services_count == 1
        assert d2.sub_services_status == DeploymentState.GOOD
        assert d2.deployment_status == DeploymentState.GOOD

    def test_sibling(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        assert d2.sub_services_count == 2

    def test_multi_level(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._label_dependency(d1, d2)
        self._label_dependency(d2, d3)
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        db.session.refresh(d3)
        assert d2.sub_services_count == 1
        assert d3.sub_services_count == 2

    def test_sibling_child(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        d4 = self._deployment(id='d4')
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        self._label_dependency(d4, d3)
        d3.sub_services_count = 42
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        # d3's child wasn't retrieved, because it's not a direct child of
        # any of d1's parents; instead, we just trust whatever count d3
        # declared (42 + d3 itself + d1)
        assert d2.sub_services_count == 44

    def test_is_env(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._label_dependency(d1, d2)
        self._label(d1, 'csys-obj-type', 'environment')
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        assert d2.sub_services_count == 0
        assert d2.sub_environments_count == 1

    def test_latest_execution_status(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        self._label_dependency(d1, d2)
        d2.latest_execution = models.Execution(
            status='failed',
            workflow_id='',
            tenant=self.tenant,
            creator=self.user,
        )
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        assert d2.deployment_status == DeploymentState.REQUIRE_ATTENTION

    def test_multiple_child_status(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        self._label_dependency(d1, d2)
        self._label_dependency(d3, d2)
        d1.deployment_status = DeploymentState.GOOD
        d3.deployment_status = DeploymentState.REQUIRE_ATTENTION
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        assert d2.sub_services_count == 2
        assert d2.sub_services_status == DeploymentState.REQUIRE_ATTENTION

    def test_override_when_fetched(self):
        d1 = self._deployment(id='d1')
        d2 = self._deployment(id='d2')
        d3 = self._deployment(id='d3')
        d4 = self._deployment(id='d4')
        self._label_dependency(d1, d2)
        self._label_dependency(d4, d2)
        self._label_dependency(d2, d3)
        # we'll be fetching d2's children, so the old 42 is going to be
        # overridden, because we'll recompute its sub-services to 2
        d2.sub_services_count = 42
        db.session.flush()
        self.rm.recalc_ancestors([d1._storage_id])
        db.session.refresh(d2)
        db.session.refresh(d3)
        assert d2.sub_services_count == 2
        assert d3.sub_services_count == 3


class TestUpdateIDDs(_DependencyTestUtils, BaseServerTestCase):
    """Tests for update_inter_deployment_dependencies

    Those tests prepare deployments, create dependencies, run the
    function-under-test, and assert that labels were created, and the IDD
    was filled in where applicable.

    Normally the IDD for testing needs to have a None target, so that
    the function can be found based on the target_deployment_func.

    Note: update_inter_deployment_dependencies is going to do actual
    select calls, bypassing the ORM, so .commit() must be called after
    the setup phase.
    """

    def test_no_idds(self):
        dep = self._deployment()
        db.session.commit()

        update_inter_deployment_dependencies(self.sm, dep)
        assert len(dep.labels) == 0
        assert len(dep.source_of_dependency_in) == 0
        assert len(dep.target_of_dependency_in) == 0

    def test_preexisting_dependency(self):
        source = self._deployment(id='source')
        target = self._deployment(id='target')
        # the dependency already existed and was set to target, we do nothing
        self._dependency(source, target)

        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0

        assert len(target.labels) == 0
        assert len(target.source_of_dependency_in) == 0
        assert len(target.target_of_dependency_in) == 1

    def test_component_dependency(self):
        source = self._deployment(id='source')
        target = self._deployment(id='target')
        self._dependency(
            source, None, dependency_creator='component.node1',
            # "target" is a function that evaluates to the string "target".
            # A very no-op one, but still evaluates, technically!
            target_deployment_func='target')

        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0

        assert len(target.labels) == 0
        assert len(target.source_of_dependency_in) == 0
        assert len(target.target_of_dependency_in) == 1

    def test_sharedresource_dependency(self):
        source = self._deployment(id='source')
        target = self._deployment(id='target')
        self._dependency(source, None,
                         dependency_creator='sharedresource.node1',
                         target_deployment_func='target')
        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0

        assert len(target.labels) == 1
        assert len(target.source_of_dependency_in) == 0
        assert len(target.target_of_dependency_in) == 1
        label = target.labels[0]
        assert label.key == 'csys-consumer-id'
        assert label.value == source.id

    def test_other_dependency(self):
        source = self._deployment(id='source')
        target = self._deployment(id='target')
        self._dependency(source, None, target_deployment_func='target')
        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0

        assert len(target.labels) == 1
        assert len(target.source_of_dependency_in) == 0
        assert len(target.target_of_dependency_in) == 1

    def test_func_dependency(self):
        source = self._deployment(id='source')
        target = self._deployment(id='target')

        idd = self._dependency(source, None, target_deployment_func='target')
        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert idd.target_deployment == target

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0

        assert len(target.labels) == 1
        assert len(target.source_of_dependency_in) == 0
        assert len(target.target_of_dependency_in) == 1
        label = target.labels[0]
        assert label.key == 'csys-consumer-id'
        assert label.value == source.id

    def test_multiple_levels(self):
        source = self._deployment(id='source')
        target = self._deployment(id='target')
        targets_target = self._deployment(id='targets_target')

        # "target" is a function that evaluates to the string "target". A very
        # no-op one, but still evaluates, technically!
        self._dependency(source, None, target_deployment_func='target')
        self._dependency(target, None, target_deployment_func='targets_target')
        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0

        assert len(target.labels) == 1
        assert len(target.source_of_dependency_in) == 1
        assert len(target.target_of_dependency_in) == 1
        label = target.labels[0]
        assert label.key == 'csys-consumer-id'
        assert label.value == source.id

        assert len(targets_target.labels) == 0
        # still 0 - we need to recalc the next level as well
        update_inter_deployment_dependencies(self.sm, target)

        assert len(targets_target.labels) == 1
        assert len(targets_target.source_of_dependency_in) == 0
        assert len(targets_target.target_of_dependency_in) == 1
        label = targets_target.labels[0]
        assert label.key == 'csys-consumer-id'
        assert label.value == target.id

    def test_self_dependency(self):
        source = self._deployment(id='source')
        self._dependency(source, None, target_deployment_func='source')
        db.session.commit()
        with self.assertRaises(ConflictError):
            update_inter_deployment_dependencies(self.sm, source)

    def test_cyclic_dependency(self):
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        self._dependency(dep1, None, target_deployment_func='dep2')
        self._dependency(dep2, None, target_deployment_func='dep1')
        db.session.commit()
        update_inter_deployment_dependencies(self.sm, dep1)
        with self.assertRaises(ConflictError):
            update_inter_deployment_dependencies(self.sm, dep2)

    def test_multilevel_dependency(self):
        dep1 = self._deployment(id='dep1')
        dep2 = self._deployment(id='dep2')
        dep3 = self._deployment(id='dep3')
        self._dependency(dep1, None, target_deployment_func='dep2')
        self._dependency(dep2, None, target_deployment_func='dep3')
        self._dependency(dep3, None, target_deployment_func='dep1')
        db.session.commit()
        update_inter_deployment_dependencies(self.sm, dep1)
        update_inter_deployment_dependencies(self.sm, dep2)
        with self.assertRaises(ConflictError):
            update_inter_deployment_dependencies(self.sm, dep3)

    def test_external_target(self):
        source = self._deployment(id='source')
        self._dependency(source, None, external_target='external-target')
        db.session.commit()

        update_inter_deployment_dependencies(self.sm, source)

        assert len(source.labels) == 0
        assert len(source.source_of_dependency_in) == 1
        assert len(source.target_of_dependency_in) == 0


class InterDeploymentDependenciesTest(BaseServerTestCase):
    def setUp(self):
        super(InterDeploymentDependenciesTest, self).setUp()
        self.dependency_creator = 'dependency_creator'
        self.source_deployment = 'source_deployment'
        self.target_deployment = 'target_deployment'
        self.dependency = create_deployment_dependency(
            self.dependency_creator,
            self.source_deployment,
            self.target_deployment)
        self.put_mock_deployments(self.source_deployment,
                                  self.target_deployment)

    def test_adds_dependency_and_retrieves_it(self):
        dependency = self.client.inter_deployment_dependencies.create(
            **self.dependency)
        response = self.client.inter_deployment_dependencies.list()
        if response:
            self.assertDictEqual(dependency, response[0])
        else:
            raise NotFoundError(**self.dependency)

    def test_deletes_existing_dependency(self):
        self.client.inter_deployment_dependencies.create(
            **self.dependency)
        self.assertEqual(
            1,
            len(self.client.inter_deployment_dependencies.list())
        )
        self.client.inter_deployment_dependencies.delete(
            **self.dependency)
        self.assertEqual(
            0,
            len(self.client.inter_deployment_dependencies.list())
        )

    def test_fails_to_delete_non_existing_dependency(self):
        message = 'not found'
        with self.assertRaisesRegex(CloudifyClientError, message) as cm:
            self.client.inter_deployment_dependencies.delete(
                **self.dependency)
        assert cm.exception.status_code == 404

    def test_list_dependencies_returns_empty_list(self):
        self.assertEqual(
            0,
            len(self.client.inter_deployment_dependencies.list())
        )

    def test_list_dependencies_returns_correct_list(self):
        dependency = self.client.inter_deployment_dependencies.create(
            **self.dependency)
        dependency_list = list(
            self.client.inter_deployment_dependencies.list())
        self.assertListEqual([dependency], dependency_list)

    def test_deployment_creation_creates_dependencies(self):
        static_target_deployment = 'shared1'
        resource_id = 'i{0}'.format(uuid.uuid4())
        self.client.secrets.create('shared2_key', 'secret')

        self.put_deployment(
            blueprint_file_name='blueprint_with_capabilities.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id=static_target_deployment)

        self.put_deployment(
            blueprint_file_name='blueprint_with_static_and_runtime'
                                '_get_capability.yaml',
            blueprint_id=resource_id,
            deployment_id=resource_id)

        dependencies = self.client.inter_deployment_dependencies.list()
        self.assertEqual(2, len(dependencies))
        target_deployment_func = self._get_target_deployment_func(dependencies)
        static_dependency = self._get_static_dependency(dependencies)

        self._assert_dependency_values(static_dependency,
                                       static_target_deployment,
                                       resource_id)
        self.assertEqual(target_deployment_func,
                         {'get_secret': 'shared2_key'})

    @staticmethod
    def _get_target_deployment_func(dependencies_list):
        for dependency in dependencies_list:
            if 'property_function' in dependency.dependency_creator:
                return dependency['target_deployment_func']

    @staticmethod
    def _get_static_dependency(dependencies_list):
        for dependency in dependencies_list:
            if 'property_static' in dependency.dependency_creator:
                return dependency

    def _assert_dependency_values(self, dependency, target_deployment_id,
                                  resource_id):
        self.assertEqual(dependency.source_deployment_id,
                         resource_id)
        self.assertEqual(dependency.target_deployment_id,
                         target_deployment_id)

    def test_alerts_uninstall_deployment(self):
        self._prepare_dependent_deployments()
        self.client.executions.start('infra', 'install')
        self.assertRaisesRegex(
            CloudifyClientError,
            '1] Deployment `app` uses a shared resource from the current '
            'deployment in its node `vm`',
            self.client.executions.start,
            'infra',
            'uninstall'
        )

    def test_alerts_delete_deployment(self):
        self._prepare_dependent_deployments()
        self.assertRaisesRegex(
            CloudifyClientError,
            '1] Deployment `app` uses a shared resource from the current '
            'deployment in its node `vm`',
            self.client.deployments.delete,
            'infra'
        )

    def test_alerts_force_uninstall_deployment_no_error(self):
        self._prepare_dependent_deployments()
        self.client.executions.start('infra', 'uninstall', force=True)

    def _prepare_dependent_deployments(self):
        self.put_deployment(
            blueprint_file_name='blueprint_with_inputs.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id='infra',
            inputs={'http_web_server_port': 80}
        )
        self.put_deployment(
            blueprint_file_name='blueprint.yaml',
            blueprint_id='i{0}'.format(uuid.uuid4()),
            deployment_id='app')
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.vm',
                                           'app',
                                           'infra'))

    def _populate_dependencies_table(self):
        self.put_mock_deployments('0', '1')
        self.put_mock_deployments('2', '3')
        self.put_mock_deployments('4', '5')
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sample.vm', '1', '0'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('capability.host', '2', '0'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('component.infra', '3', '2'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.infra', '3', '1'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('sharedresource.mynode', '4', '0'))
        self.client.inter_deployment_dependencies.create(
            **create_deployment_dependency('capability.ip', '5', '4'))

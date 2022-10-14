from datetime import datetime
from cloudify.models_states import DeploymentState, ExecutionState
from manager_rest.test import base_test
from manager_rest.storage import models, db

from manager_rest.snapshot_utils import (populate_deployment_statuses,
                                         migrate_pickle_to_json)


class TestSnapshotDeploymentStatus(base_test.BaseServerTestCase):
    def setUp(self):
        super(TestSnapshotDeploymentStatus, self).setUp()
        self._tenant = models.Tenant()
        self._user = models.User()

    def tearDown(self):
        db.session.rollback()
        super(TestSnapshotDeploymentStatus, self).tearDown()

    def _make_blueprint(self, **kw):
        bp = models.Blueprint(tenant=self._tenant, creator=self._user, **kw)
        db.session.add(bp)
        db.session.flush()
        return bp

    def _make_deployment(self, **kw):
        bp = models.Blueprint(tenant=self._tenant, creator=self._user)
        dep = models.Deployment(
            blueprint=bp,
            creator=self._user,
            tenant=self._tenant,
            display_name='',
            **kw,
        )
        db.session.add(dep)
        db.session.flush()
        return dep

    def _make_dep_mod(self, dep, **kw):
        dep_mod = models.DeploymentModification(
            deployment=dep,
            creator=self._user,
            tenant=self._tenant,
            **kw,
        )
        db.session.add(dep_mod)
        db.session.flush()
        return dep_mod

    def _make_dep_upd(self, dep, **kw):
        dep_upd = models.DeploymentUpdate(
            deployment=dep,
            creator=self._user,
            tenant=self._tenant,
            **kw,
        )
        db.session.add(dep_upd)
        db.session.flush()
        return dep_upd

    def _make_execution(self, **kw):
        execution = models.Execution(
            workflow_id='test',
            tenant=self._tenant,
            creator=self._user,
            **kw,
        )
        db.session.add(execution)
        db.session.flush()
        return execution

    def _make_node(self, dep, **kw):
        node = models.Node(
            deployment=dep,
            deploy_number_of_instances=0,
            max_number_of_instances=1,
            min_number_of_instances=1,
            number_of_instances=1,
            planned_number_of_instances=1,
            type='cloudify.nodes.Root',
            creator=self._user,
            tenant=self._tenant,
            **kw,
        )
        db.session.add(node)
        db.session.flush()
        return node

    def _make_instance(self, node, state='uninitialized', **kw):
        ni = models.NodeInstance(
            node=node,
            state=state,
            creator=self._user,
            tenant=self._tenant,
            **kw,
        )
        db.session.add(ni)
        db.session.flush()
        return ni

    def _make_plugin(self, **kw):
        plugin = models.Plugin(
            archive_name='test',
            package_name='test',
            uploaded_at='2000-01-01 00:00:00',
            creator=self._user,
            tenant=self._tenant,
            **kw
        )
        db.session.add(plugin)
        db.session.flush()
        return plugin

    def _make_plugins_update(self, blueprint, execution, **kw):
        plugins_update = models.PluginsUpdate(
            blueprint=blueprint,
            temp_blueprint=blueprint,
            execution=execution,
            creator=self._user,
            tenant=self._tenant,
            **kw
        )
        db.session.add(plugins_update)
        db.session.flush()
        return plugins_update

    def test_latest_execution_empty(self):
        dep = self._make_deployment()
        populate_deployment_statuses()
        dep = models.Deployment.query.get(dep._storage_id)
        assert dep.latest_execution is None

    def test_latest_execution_one(self):
        dep = self._make_deployment()
        exc = models.Execution(deployment=dep, workflow_id='x')
        db.session.add(exc)
        db.session.flush()
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.latest_execution == exc

    def test_latest_execution_multiple(self):
        dep1 = self._make_deployment()
        dep2 = self._make_deployment()
        exc1 = models.Execution(deployment=dep1, workflow_id='x')
        exc2 = models.Execution(deployment=dep2, workflow_id='x',
                                created_at=datetime(2020, 1, 1))
        exc3 = models.Execution(deployment=dep2, workflow_id='x',
                                created_at=datetime(2019, 1, 1))
        db.session.add_all([exc1, exc2, exc3])
        db.session.flush()
        populate_deployment_statuses()
        db.session.refresh(dep1)
        db.session.refresh(dep2)
        assert dep1.latest_execution == exc1
        assert dep2.latest_execution == exc2

    def test_node_instances_empty(self):
        dep = self._make_deployment()
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.installation_status == DeploymentState.ACTIVE

    def test_node_instances_not_started(self):
        dep = self._make_deployment()
        node = self._make_node(dep)
        self._make_instance(node)
        self._make_instance(node, state='started')
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.installation_status == DeploymentState.INACTIVE

    def test_node_instances_started(self):
        dep = self._make_deployment()
        node = self._make_node(dep)
        self._make_instance(node, state='started')
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.installation_status == DeploymentState.ACTIVE

    def test_node_instances_multiple(self):
        dep1 = self._make_deployment()
        dep2 = self._make_deployment()
        node1 = self._make_node(dep1)
        node2 = self._make_node(dep2)
        self._make_instance(node1)
        self._make_instance(node1, state='started')
        self._make_instance(node2, state='started')
        self._make_instance(node2, state='started')
        populate_deployment_statuses()
        db.session.refresh(dep1)
        db.session.refresh(dep2)
        assert dep1.installation_status == DeploymentState.INACTIVE
        assert dep2.installation_status == DeploymentState.ACTIVE

    def test_deployment_status_good(self):
        dep = self._make_deployment()
        exc = models.Execution(
            deployment=dep, workflow_id='x', status=ExecutionState.TERMINATED)
        db.session.add(exc)
        db.session.flush()
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.deployment_status == DeploymentState.GOOD

    def test_deployment_status_in_progress(self):
        dep = self._make_deployment()
        exc = models.Execution(
            deployment=dep, workflow_id='x', status=ExecutionState.STARTED)
        db.session.add(exc)
        db.session.flush()
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.deployment_status == DeploymentState.IN_PROGRESS

    def test_deployment_status_failed_execution(self):
        dep = self._make_deployment()
        exc = models.Execution(
            deployment=dep, workflow_id='x', status=ExecutionState.FAILED)
        db.session.add(exc)
        db.session.flush()
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.deployment_status == DeploymentState.REQUIRE_ATTENTION

    def test_deployment_status_inactive(self):
        dep = self._make_deployment()
        node = self._make_node(dep)
        self._make_instance(node)
        exc = models.Execution(
            deployment=dep, workflow_id='x', status=ExecutionState.TERMINATED)
        db.session.add(dep)
        db.session.add(exc)
        db.session.flush()
        populate_deployment_statuses()
        db.session.refresh(dep)
        assert dep.deployment_status == DeploymentState.REQUIRE_ATTENTION

    def test_pickle_to_json_blueprints(self):
        silly_plan = {'first': 'foo', 'then': ['bar', 'baz', 3.14, True, -1]}
        bp = self._make_blueprint(id='bp', plan_p=silly_plan)
        assert bp.plan is None
        migrate_pickle_to_json()
        assert silly_plan == bp.plan

    def test_pickle_to_json_deployments(self):
        silly_capabilities = {'what': 'ever'}
        silly_groups = (-2, -1, 0, 1, )
        silly_inputs = {'one': {'type': 'string', 'value': 'qwerty'}}
        silly_policy_triggers = {'some': 'thing'}
        silly_policy_types = ['foo', 'bar']
        silly_scaling_groups = 3.14
        silly_workflows = "Lorem ipsum"
        dep = self._make_deployment(
            capabilities_p=silly_capabilities,
            groups_p=silly_groups,
            inputs_p=silly_inputs,
            policy_triggers_p=silly_policy_triggers,
            policy_types_p=silly_policy_types,
            scaling_groups_p=silly_scaling_groups,
            workflows_p=silly_workflows,
        )
        assert dep.capabilities is None
        assert dep.groups is None
        assert dep.inputs is None
        assert dep.policy_triggers is None
        assert dep.policy_types is None
        assert dep.scaling_groups is None
        assert dep.workflows is None
        migrate_pickle_to_json()
        assert silly_capabilities == dep.capabilities
        assert silly_groups == dep.groups
        assert silly_inputs == dep.inputs
        assert silly_policy_triggers == dep.policy_triggers
        assert silly_policy_types == dep.policy_types
        assert silly_scaling_groups == dep.scaling_groups
        assert silly_workflows == dep.workflows

    def test_pickle_to_json_deployment_modifications(self):
        silly_context = {'some': 'thing'}
        silly_modified_nodes = (-2, -1, 0, 1, )
        silly_node_instances = [{'quick': 1}, {'brown': 2}, {'fox': 3}]
        dep_mod = self._make_dep_mod(
            self._make_deployment(),
            context_p=silly_context,
            modified_nodes_p=silly_modified_nodes,
            node_instances_p=silly_node_instances,
        )
        assert dep_mod.context is None
        assert dep_mod.modified_nodes is None
        assert dep_mod.node_instances is None
        migrate_pickle_to_json()
        assert silly_context == dep_mod.context
        assert silly_modified_nodes == dep_mod.modified_nodes
        assert silly_node_instances == dep_mod.node_instances

    def test_pickle_to_json_deployment_updates(self):
        silly_deployment_plan = {'some': 'thing'}
        silly_deployment_update_nis = {'lorem': None}
        silly_deployment_update_deployment = 3.14
        silly_central_plugins_to_uninstall = (-2, -1, 0, 1, )
        silly_central_plugins_to_install = {'foo': [1, 2], 'bar': ['3', '4']}
        silly_deployment_update_nodes = -999999
        silly_modified_entity_ids = ['q', 'w', 'e', ]
        silly_old_inputs = {'this': ['is', 'something']}
        silly_new_inputs = {'some': 'thing'}
        dep_upd = self._make_dep_upd(
            self._make_deployment(),
            deployment_plan_p=silly_deployment_plan,
            deployment_update_node_instances_p=silly_deployment_update_nis,
            deployment_update_deployment_p=silly_deployment_update_deployment,
            central_plugins_to_uninstall_p=silly_central_plugins_to_uninstall,
            central_plugins_to_install_p=silly_central_plugins_to_install,
            deployment_update_nodes_p=silly_deployment_update_nodes,
            modified_entity_ids_p=silly_modified_entity_ids,
            old_inputs_p=silly_old_inputs,
            new_inputs_p=silly_new_inputs,
        )
        assert dep_upd.deployment_plan is None
        assert dep_upd.deployment_update_node_instances is None
        assert dep_upd.deployment_update_deployment is None
        assert dep_upd.central_plugins_to_uninstall is None
        assert dep_upd.central_plugins_to_install is None
        assert dep_upd.deployment_update_nodes is None
        assert dep_upd.modified_entity_ids is None
        assert dep_upd.old_inputs is None
        assert dep_upd.new_inputs is None
        migrate_pickle_to_json()
        assert silly_deployment_plan == dep_upd.deployment_plan
        assert silly_deployment_update_nis ==\
               dep_upd.deployment_update_node_instances
        assert silly_deployment_update_deployment ==\
               dep_upd.deployment_update_deployment
        assert silly_central_plugins_to_uninstall ==\
               dep_upd.central_plugins_to_uninstall
        assert silly_central_plugins_to_install ==\
               dep_upd.central_plugins_to_install
        assert silly_deployment_update_nodes == dep_upd.deployment_update_nodes
        assert silly_modified_entity_ids == dep_upd.modified_entity_ids
        assert silly_old_inputs == dep_upd.old_inputs
        assert silly_new_inputs == dep_upd.new_inputs

    def test_pickle_to_json_executions(self):
        silly_parameters = {'first': 'foo', 'then': ['bar', True, -1]}
        execution = self._make_execution(parameters_p=silly_parameters)
        assert execution.parameters is None
        migrate_pickle_to_json()
        assert silly_parameters == execution.parameters

    def test_pickle_to_json_nodes(self):
        silly_plugins = {'lorem': 'ipsum'}
        silly_plugins_to_install = [1, 2, 3, ]
        silly_properties = 'Lorem ipsum'
        silly_relationships = {'a': {'somewhat': {'nested': {'dict': True}}}}
        silly_operations = {'bwaha': 'ha'}
        silly_type_hierarchy = {'string': {'derived_from': 'float'}}
        node = self._make_node(
            self._make_deployment(),
            plugins_p=silly_plugins,
            plugins_to_install_p=silly_plugins_to_install,
            properties_p=silly_properties,
            relationships_p=silly_relationships,
            operations_p=silly_operations,
            type_hierarchy_p=silly_type_hierarchy,
        )
        assert node.plugins is None
        assert node.plugins_to_install is None
        assert node.properties is None
        assert node.relationships is None
        assert node.operations is None
        assert node.type_hierarchy is None
        migrate_pickle_to_json()
        assert silly_plugins == node.plugins
        assert silly_plugins_to_install == node.plugins_to_install
        assert silly_properties == node.properties
        assert silly_relationships == node.relationships
        assert silly_operations == node.operations
        assert silly_type_hierarchy == node.type_hierarchy

    def test_pickle_to_json_node_instances(self):
        silly_relationships = {'lorem': 'ipsum'}
        silly_runtime_properties = [1, 2, 3, ]
        silly_scaling_groups = {'a': {'somewhat': {'nested': {'dict': True}}}}
        node_instance = self._make_instance(
            self._make_node(self._make_deployment()),
            relationships_p=silly_relationships,
            runtime_properties_p=silly_runtime_properties,
            scaling_groups_p=silly_scaling_groups,
        )
        assert node_instance.relationships is None
        assert node_instance.runtime_properties is None
        assert node_instance.scaling_groups is None
        migrate_pickle_to_json()
        assert silly_relationships == node_instance.relationships
        assert silly_runtime_properties == node_instance.runtime_properties
        assert silly_scaling_groups == node_instance.scaling_groups

    def test_pickle_to_json_plugins(self):
        silly_excluded_wheels = (-2, -1, 0, 1,)
        silly_supported_platform = {'lorem': 'ipsum'}
        silly_supported_py_versions = [1, 2, 3, ]
        silly_wheels = {'a': {'somewhat': {'nested': {'dict': True}}}}
        plugin = self._make_plugin(
            excluded_wheels_p=silly_excluded_wheels,
            supported_platform_p=silly_supported_platform,
            supported_py_versions_p=silly_supported_py_versions,
            wheels_p=silly_wheels,
        )
        assert plugin.excluded_wheels is None
        assert plugin.supported_platform is None
        assert plugin.supported_py_versions is None
        assert plugin.wheels is None
        migrate_pickle_to_json()
        assert silly_excluded_wheels == plugin.excluded_wheels
        assert silly_supported_platform == plugin.supported_platform
        assert silly_supported_py_versions == plugin.supported_py_versions
        assert silly_wheels == plugin.wheels

    def test_pickle_to_json_plugins_updates(self):
        silly_deployments_to_update = {'lorem': (-2, -1, 0, 1,)}
        plug_upd = self._make_plugins_update(
            self._make_blueprint(),
            self._make_execution(),
            deployments_to_update_p=silly_deployments_to_update,
        )
        assert plug_upd.deployments_to_update is None
        migrate_pickle_to_json()
        assert silly_deployments_to_update == plug_upd.deployments_to_update

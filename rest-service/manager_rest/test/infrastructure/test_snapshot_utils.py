from datetime import datetime
from cloudify.models_states import DeploymentState, ExecutionState
from manager_rest.test import base_test
from manager_rest.storage import models, db

from manager_rest.snapshot_utils import populate_deployment_statuses


class TestSnapshotDeploymentStatus(base_test.BaseServerTestCase):
    def setUp(self):
        super(TestSnapshotDeploymentStatus, self).setUp()
        self._tenant = models.Tenant()
        self._user = models.User()

    def tearDown(self):
        db.session.rollback()
        super(TestSnapshotDeploymentStatus, self).tearDown()

    def _make_deployment(self):
        bp = models.Blueprint(tenant=self._tenant, creator=self._user)
        dep = models.Deployment(
            blueprint=bp,
            creator=self._user,
            tenant=self._tenant,
            display_name='',
        )
        db.session.add(dep)
        db.session.flush()
        return dep

    def _make_node(self, dep):
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
        )
        db.session.add(node)
        db.session.flush()
        return node

    def _make_instance(self, node, state='uninitialized'):
        ni = models.NodeInstance(
            node=node,
            state=state,
            creator=self._user,
            tenant=self._tenant
        )
        db.session.add(ni)
        db.session.flush()
        return ni

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

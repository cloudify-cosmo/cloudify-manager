from manager_rest.storage import models
from manager_rest.test import base_test


class TestUsageCollectorTriggers(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        # Create dummy usage collector entry in DB
        self.sm.put(models.UsageCollector(
            manager_id=123456, hours_interval=4, days_interval=1))

    def test_max_total_deployments(self):
        bp = models.Blueprint(
            id='blueprint',
            creator=self.user,
            tenant=self.tenant,
        )
        models.Deployment(
            id='d1',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        models.Deployment(
            id='d2',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        self.delete_deployment('d2')
        models.Deployment(
            id='d3',
            blueprint=bp,
            creator=self.user,
            tenant=self.tenant,
        )
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.max_deployments == 2
        assert usage_metrics.total_deployments == 3

    def test_max_total_blueprints(self):
        bp = models.Blueprint(
            id='bp1',
            creator=self.user,
            tenant=self.tenant,
        )
        self.client.blueprints.delete(bp.id)
        models.Blueprint(
            id='bp2',
            creator=self.user,
            tenant=self.tenant,
        )
        models.Blueprint(
            id='bp3',
            creator=self.user,
            tenant=self.tenant,
        )
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.max_blueprints == 2
        assert usage_metrics.total_blueprints == 3

    def test_total_executions(self):
        for num in range(2):
            models.Execution(
                id=f'exc{num}',
                workflow_id='wf1',
                is_system_workflow=True,
                creator=self.user,
                tenant=self.tenant,
            )
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.total_executions == 2

    def test_max_tenants(self):
        base_max_tenants = len(self.client.tenants.list())
        t1 = self.sm.put(models.Tenant(name='t1'))
        t2 = self.sm.put(models.Tenant(name='t2'))
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.max_tenants == base_max_tenants + 2

        self.sm.delete(t1)
        self.sm.delete(t2)
        self.sm.put(models.Tenant(name='t3'))
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.max_tenants == base_max_tenants + 2

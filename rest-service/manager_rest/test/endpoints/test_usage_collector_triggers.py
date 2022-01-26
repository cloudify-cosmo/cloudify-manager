from manager_rest.storage import models
from manager_rest.test import base_test


class TestUsageCollectorTriggers(base_test.BaseServerTestCase):
    def setUp(self):
        super().setUp()
        # Create dummy usage collector entry in DB
        self.sm.put(models.UsageCollector(
            manager_id=123456, hours_interval=4, days_interval=1))

    def test_max_total_deployments(self):
        self.put_blueprint()
        self.client.deployments.create('blueprint', 'd1')
        self.client.deployments.create('blueprint', 'd2')
        self.delete_deployment('d2')
        self.client.deployments.create('blueprint', 'd3')
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.max_deployments == 2
        assert usage_metrics.total_deployments == 3

    def test_max_total_blueprints(self):
        self.put_blueprint(blueprint_id='bp1')
        self.client.blueprints.delete('bp1')
        self.put_blueprint(blueprint_id='bp2')
        self.put_blueprint(blueprint_id='bp3')
        usage_metrics = models.UsageCollector.query.first()
        assert usage_metrics.max_blueprints == 2
        assert usage_metrics.total_blueprints == 3

    def test_total_executions(self):
        self.put_deployment('d1')
        # this executes upload_blueprint and create_deployment_environment
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

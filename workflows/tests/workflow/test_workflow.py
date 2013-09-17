__author__ = 'idanm'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import logger


class celery_worker_queue:
    def __init__(self, queue_name=None):
        self.queue_name = queue_name

    def __call__(self, method):
        def decorated_method(*args):
            method(*args)
        return decorated_method


class TestRuoteWorkflows(TestCase):

    def test_execute_operation(self):
        dsl_path = resource("dsl/basic.yaml")

        from cosmo.appdeployer.tasks import deploy
        logger.info("deploying dsl...")
        result = deploy.delay(dsl_path)
        result.get(timeout=120)

        from cosmo.cloudmock.tasks import get_machines
        logger.info("getting machines info...")
        result = get_machines.apply_async()

        machines = result.get(timeout=10)
        self.assertEquals(1, len(machines))



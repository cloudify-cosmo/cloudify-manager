import datetime

from integration_tests import AgentlessTestCase
from integration_tests.framework import utils
from integration_tests.tests.utils import (
    do_retries,
    get_resource as resource)


class ExecutionsSchedulesTest(AgentlessTestCase):

    def test_schedule_execution(self):
        deployment = self.deploy(resource("dsl/basic.yaml"))

        # schedule 3 runs of `install`
        schedule = self.client.execution_schedules.create(
            'sched-1', deployment.id, 'install', since=datetime.now(),
            frequency='1 min', count=3)

        import pydevd
        pydevd.settrace('192.168.43.135', port=53100, stdoutToServer=True,
                        stderrToServer=True)

    def test_schedule_execution_queue_simultaneous_execs(self):
        pass

    def test_schedule_execution_stop_on_fail(self):
        pass

    def test_schedule_execution_continue_on_fail(self):
        pass

    def test_schedule_execution_slip_shorter_than_downtime(self):
        pass

    def test_schedule_execution_slip_longer_than_downtime(self):
        pass

    def test_schedule_executions_disable_and_enable(self):
        # TODO:: add when we have this option
        pass

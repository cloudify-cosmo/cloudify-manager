from datetime import datetime, timedelta

from manager_rest.test.attribute import attr
from manager_rest.test.base_test import BaseServerTestCase, LATEST_API_VERSION

from cloudify_rest_client.exceptions import CloudifyClientError


@attr(client_min_version=LATEST_API_VERSION,
      client_max_version=LATEST_API_VERSION)
class ExecutionSchedulesTestCase(BaseServerTestCase):

    DEPLOYMENT_ID = 'deployment'
    fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
    an_hour_from_now = \
        datetime.utcnow().replace(microsecond=0) + timedelta(hours=1)
    two_hours_from_now = \
        datetime.utcnow().replace(microsecond=0) + timedelta(hours=2)
    three_hours_from_now = \
        datetime.utcnow().replace(microsecond=0) + timedelta(hours=3)
    three_weeks_from_now = \
        datetime.utcnow().replace(microsecond=0) + timedelta(weeks=3)
    deployment_id = None

    def setUp(self):
        super(ExecutionSchedulesTestCase, self).setUp()
        _, self.deployment_id, _, _ = self.put_deployment(self.DEPLOYMENT_ID)

    def test_schedule_create(self):
        schedule_id = 'sched-1'
        workflow_id = 'install'
        schedule = self.client.execution_schedules.create(
            schedule_id, self.deployment_id, workflow_id,
            since=self.an_hour_from_now, recurrence='1 minutes', count=5)

        self.assertEqual(schedule.id, schedule_id)
        self.assertEqual(schedule.deployment_id, self.deployment_id)
        self.assertEqual(schedule.workflow_id, workflow_id)
        self.assertEqual(datetime.strptime(schedule.since, self.fmt),
                         self.an_hour_from_now)
        self.assertEqual(len(schedule['all_next_occurrences']), 5)
        self.assertEqual(
            datetime.strptime(schedule['next_occurrence'], self.fmt),
            self.an_hour_from_now)
        self.assertEqual(schedule['slip'], 0)
        self.assertEqual(schedule['stop_on_fail'], False)

    def test_schedule_create_weekdays(self):
        schedule = self.client.execution_schedules.create(
            'sched-weekdays', self.deployment_id, 'install',
            since=self.an_hour_from_now, until=self.three_weeks_from_now,
            recurrence='1 days', weekdays=['mo', 'tu', 'we', 'th'])
        self.assertEqual(len(schedule['all_next_occurrences']), 12)  # 3w * 4d

    def test_schedules_list(self):
        schedule_ids = ['sched-1', 'sched-2']
        for schedule_id in schedule_ids:
            self.client.execution_schedules.create(
                schedule_id, self.deployment_id, 'install',
                since=self.an_hour_from_now, recurrence='1 minutes', count=5)

        schedules = self.client.execution_schedules.list()
        self.assertEqual(len(schedules), 2)
        self.assertSetEqual({s.id for s in schedules}, set(schedule_ids))

    def test_schedule_delete(self):
        self.client.execution_schedules.create(
            'delete-me', self.deployment_id, 'install',
            since=self.an_hour_from_now, recurrence='1 minutes', count=5)
        self.assertEqual(len(self.client.execution_schedules.list()), 1)
        self.client.execution_schedules.delete('delete-me', self.deployment_id)
        self.assertEqual(len(self.client.execution_schedules.list()), 0)

    def test_schedule_update(self):
        schedule = self.client.execution_schedules.create(
            'update-me', self.deployment_id, 'install',
            since=self.an_hour_from_now, until=self.two_hours_from_now,
            recurrence='1 minutes')

        # `until` is inclusive
        self.assertEqual(len(schedule['all_next_occurrences']), 61)
        self.assertEqual(schedule['rule']['recurrence'], '1 minutes')
        self.assertEqual(schedule['slip'], 0)

        self.client.execution_schedules.update(
            'update-me', self.deployment_id, recurrence='5 minutes', slip=30)

        # get the schedule from the DB and not directly from .update endpoint
        schedule = self.client.execution_schedules.get('update-me',
                                                       self.deployment_id)

        self.assertEqual(len(schedule['all_next_occurrences']), 13)  # 60/5+1
        self.assertEqual(schedule['rule']['recurrence'], '5 minutes')
        self.assertEqual(schedule['slip'], 30)

        self.client.execution_schedules.update(
            'update-me', self.deployment_id, until=self.three_hours_from_now)
        schedule = self.client.execution_schedules.get('update-me',
                                                       self.deployment_id)
        self.assertEqual(len(schedule['all_next_occurrences']), 25)  # 2*60/5+1

    def test_schedule_get_invalid_id(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            '404: Requested `ExecutionSchedule` .* was not found',
            self.client.execution_schedules.get,
            'nonsuch',
            self.deployment_id
        )

    def test_schedule_create_no_since(self):
        self.assertRaises(
            AssertionError,
            self.client.execution_schedules.create,
            'some_id', self.deployment_id, 'some_workflow',
            recurrence='1 minutes', count=5
        )

    def test_schedule_create_invalid_time_format(self):
        self.assertRaisesRegex(
            AttributeError,
            "'str' object has no attribute 'isoformat'",
            self.client.execution_schedules.create,
            'some_id', self.deployment_id, 'install',
            since='long ago', recurrence='1 minutes', count=5
        )

    def test_schedule_create_invalid_workflow(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            '400: Workflow some_workflow does not exist',
            self.client.execution_schedules.create,
            'some_id', self.deployment_id, 'some_workflow',
            since=self.an_hour_from_now, recurrence='1 minutes', count=5,
        )

    def test_schedule_invalid_weekdays(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            '400:.* invalid weekday',
            self.client.execution_schedules.create,
            'bad-weekdays', self.deployment_id, 'install',
            since=self.an_hour_from_now, recurrence='4 hours',
            weekdays=['oneday', 'someday']
        )
        self.client.execution_schedules.create(
            'good-weekdays', self.deployment_id, 'install',
            since=self.an_hour_from_now, recurrence='4 hours', count=6,
            weekdays=['mo', 'tu']
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            '400:.* invalid weekday',
            self.client.execution_schedules.update,
            'good-weekdays', self.deployment_id, weekdays=['oneday', 'someday']
        )

    def test_schedule_create_invalid_complex_weekdays(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            '400:.* invalid weekday',
            self.client.execution_schedules.create,
            'bad-complex-wd', self.deployment_id, 'install',
            since=self.an_hour_from_now, recurrence='4 hours',
            weekdays=['5tu']
        )

    def test_schedule_create_invalid_recurrence_with_complex_weekdays(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            '400:.* complex weekday expression',
            self.client.execution_schedules.create,
            'bad-complex-wd', self.deployment_id, 'install',
            since=self.an_hour_from_now, recurrence='4 hours',
            weekdays=['2mo', 'l-tu']
        )

    def test_schedule_invalid_repetition_without_recurrence(self):
        recurrence_error = \
            '400: recurrence must be specified for execution count ' \
            'larger than 1'

        self.assertRaisesRegex(
            CloudifyClientError,
            recurrence_error,
            self.client.execution_schedules.create,
            'no-recurrence-no-count', self.deployment_id, 'uninstall',
            since=self.an_hour_from_now, weekdays=['su', 'mo', 'tu'],
        )
        self.client.execution_schedules.create(
            'no-recurrence-count-1', self.deployment_id, 'install',
            since=self.an_hour_from_now, count=1,
        )
        self.assertRaisesRegex(
            CloudifyClientError,
            recurrence_error,
            self.client.execution_schedules.update,
            'no-recurrence-count-1', self.deployment_id, count=2
        )

    def test_schedule_create_invalid_recurrence(self):
        self.assertRaisesRegex(
            CloudifyClientError,
            '400: `10 doboshes` is not a legal recurrence expression.',
            self.client.execution_schedules.create,
            'bad-freq', self.deployment_id, 'install',
            since=self.an_hour_from_now, recurrence='10 doboshes'
        )

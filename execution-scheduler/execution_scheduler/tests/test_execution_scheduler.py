import mock
import time

from datetime import datetime, timedelta
from dateutil import parser as date_parser

from manager_rest import utils
from manager_rest.storage import models
from manager_rest.flask_utils import setup_flask_app

from execution_scheduler.main import try_run, should_run, LoopTimer


def _get_mock_schedule(schedule_id='default', next_occurrence=None,
                       rule={'recurrence': '1 min'}, slip=0,
                       stop_on_fail=False, latest_execution=None,
                       enabled=True):
    now = utils.get_formatted_timestamp()
    blueprint = models.Blueprint(
            id='mock-bp',
            created_at=now,
            updated_at=now,
            main_file_name='abcd',
            plan={})
    deployment = models.Deployment(
        id='mock-depl',
        created_at=now,
        updated_at=now,
    )
    deployment.blueprint = blueprint
    schedule = models.ExecutionSchedule(
        _storage_id=1,
        id=schedule_id,
        deployment=deployment,
        created_at=now,
        since=now,
        until=None,
        rule=rule,
        slip=slip,
        workflow_id='install',
        parameters=None,
        execution_arguments={},
        stop_on_fail=stop_on_fail,
        next_occurrence=next_occurrence or now,
        latest_execution=latest_execution,
        enabled=enabled
    )
    return schedule


@mock.patch('manager_rest.storage.storage_utils.db')
@mock.patch('execution_scheduler.main.get_storage_manager')
@mock.patch('manager_rest.resource_manager.ResourceManager.execute_workflow')
def test_try_run_schedule(mock_execute_workflow, mock_get_sm, mock_db):
    sm = mock_get_sm()
    next_occurrence = datetime.strftime(datetime.utcnow(), '%Y-%m-%d %H:%M:%S')
    schedule = _get_mock_schedule(next_occurrence=next_occurrence)
    with setup_flask_app().app_context():
        try_run(schedule, sm)
    mock_execute_workflow.assert_called_once()

    mock_db_call_args = [call.args for call in mock_db.method_calls]
    assert 'try_advisory_lock' in mock_db_call_args[0][0]
    assert 'advisory_unlock' in mock_db_call_args[1][0]
    for call_arg in mock_db_call_args:
        assert call_arg[1]['lock_number'] == 10001

    start_time = date_parser.parse(next_occurrence)
    assert (schedule.next_occurrence - start_time).seconds == 60


@mock.patch('execution_scheduler.main.try_acquire_lock_on_table')
@mock.patch('execution_scheduler.main.get_storage_manager')
@mock.patch('execution_scheduler.main.should_run')
def test_try_run_schedule_locked(mock_should_run, mock_get_sm, mock_lock):
    mock_lock.return_value = False
    sm = mock_get_sm()
    next_occurrence = datetime.strftime(datetime.utcnow(), '%Y-%m-%d %H:%M:%S')
    schedule = _get_mock_schedule(next_occurrence=next_occurrence)
    with setup_flask_app().app_context():
        try_run(schedule, sm)
    # should_run should not run, and next occurrence won't be updated
    mock_should_run.assert_not_called()
    assert schedule.next_occurrence == next_occurrence


def test_should_run_stop_on_fail():
    schedule = _get_mock_schedule(
        stop_on_fail=True,
        latest_execution=models.Execution(status='failed'))
    assert not should_run(schedule)
    assert not schedule.enabled


def test_should_run_dont_stop_on_fail():
    schedule = _get_mock_schedule(
        stop_on_fail=False,
        latest_execution=models.Execution(status='failed'))
    assert should_run(schedule)
    assert schedule.enabled


def test_should_run_skip_if_last_execution_unfinished():
    schedule = _get_mock_schedule(
        latest_execution=models.Execution(status='started'))
    assert not should_run(schedule)


def test_should_run_slip_longer_than_downtime():
    # set slip to 3 minutes, next occurrence slated to 3 minuted ago
    # Note: should_run gives a 1 minute "grace" on top of what's set slip by
    # the user, to account for check_schedules() running every 1 minute
    next_occurrence = datetime.strftime(
        datetime.utcnow() - timedelta(minutes=3), '%Y-%m-%d %H:%M:%S')
    schedule = _get_mock_schedule(next_occurrence=next_occurrence, slip=3)
    assert should_run(schedule)


def test_should_run_slip_shorter_than_downtime():
    next_occurrence = datetime.strftime(
        datetime.utcnow() - timedelta(minutes=3), '%Y-%m-%d %H:%M:%S')
    schedule = _get_mock_schedule(next_occurrence=next_occurrence, slip=2)
    assert not should_run(schedule)


def test_loop_timer():
    _assert_loop_interval(3.42, 5)
    _assert_loop_interval(4.9, 5)
    _assert_loop_interval(0, 5)
    _assert_loop_interval(8.6, 10)


def _assert_loop_interval(work_time, assert_val, interval=5):
    a = time.time()
    with LoopTimer(interval) as t:
        time.sleep(work_time)  # imitate some job
    time.sleep(t.seconds_wait)
    b = time.time()
    assert round(b - a, 2) == assert_val

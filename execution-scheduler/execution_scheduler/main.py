import time
import logging
import argparse

import dateutil.parser
from contextlib import contextmanager
from datetime import datetime, timedelta

from manager_rest import config
from manager_rest.storage import models, get_storage_manager
from manager_rest.utils import set_current_tenant
from manager_rest.flask_utils import setup_flask_app
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage.models_base import db
from manager_rest.storage.storage_utils import (try_acquire_lock_on_table,
                                                unlock_table)


logger = logging.getLogger(__name__)
DEFAULT_INTERVAL = 60
SCHEDULER_LOCK_BASE = 10000
# so we won't conflict with usage collector, which uses lock numbers 1 and 2

DEFAULT_LOG_PATH = '/var/log/cloudify/execution-scheduler/scheduler.log'


class LoopTimer(object):
    def __init__(self, interval=DEFAULT_INTERVAL):
        self.interval = interval

    def __enter__(self):
        self.time = datetime.now()
        return self

    def __exit__(self, type, value, traceback):
        delta = (datetime.now() - self.time).total_seconds()
        self.seconds_wait = (self.interval - delta) % self.interval


def check_schedules():
    logger.debug('Checking schedules...')
    sm = get_storage_manager()
    schedules = sm.full_access_list(
        models.ExecutionSchedule,
        filters={
            models.ExecutionSchedule.enabled: True,
            models.ExecutionSchedule.next_occurrence:
            lambda x: x < datetime.utcnow()
        }
    )
    if not schedules:
        db.session.rollback()
        return

    for schedule in schedules:
        lock_num = SCHEDULER_LOCK_BASE + schedule._storage_id
        with scheduler_lock(lock_num) as locked:
            if not locked:
                logger.warning('Another manager currently runs this '
                               'schedule: %s', schedule.id)
                db.session.rollback()
                continue

            logger.debug('Acquired lock for schedule %s in DB', schedule.id)
            next_occurrence = schedule.compute_next_occurrence()
            old_next_occurrence = schedule.next_occurrence
            logger.info('Schedule: %s next in %s; old next was %s',
                        schedule.id, next_occurrence, old_next_occurrence)

            if should_run(schedule):
                execution = execute_workflow(schedule)
                schedule.latest_execution = execution
            schedule.next_occurrence = next_occurrence
            sm.update(schedule)


@contextmanager
def scheduler_lock(lock_number):
    locked = try_acquire_lock_on_table(lock_number)
    try:
        yield locked
    finally:
        if locked:
            unlock_table(lock_number)


def should_run(schedule):
    # TODO :: also, don't run if the latest execution is not in an END_STATE
    slip = timedelta(minutes=schedule.slip, seconds=60)
    next_occurrence = dateutil.parser.parse(schedule.next_occurrence,
                                            ignoretz=True)
    return datetime.utcnow() - next_occurrence < slip


def execute_workflow(schedule):
    rm = get_resource_manager()
    set_current_tenant(schedule.tenant)
    logger.info('Running: %s', schedule)

    # always queue an execution which couldn't start
    execution_arguments = schedule.execution_arguments or {}
    execution_arguments['queue'] = True

    try:
        return rm.execute_workflow(
            deployment_id=schedule.deployment.id,
            workflow_id=schedule.workflow_id,
            parameters=schedule.parameters,
            execution_creator=schedule.creator,
            **schedule.execution_arguments
        )
    finally:
        set_current_tenant(None)


def main():
    while True:
        with LoopTimer() as t:
            check_schedules()
        time.sleep(t.seconds_wait)


def cli():
    with setup_flask_app().app_context():
        config.instance.load_configuration()
    parser = argparse.ArgumentParser()
    parser.add_argument('--logfile', default=DEFAULT_LOG_PATH,
                        help='Path to the log file')
    parser.add_argument('--log-level', dest='loglevel', default='INFO',
                        help='Logging level')
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel.upper(),
                        filename=args.logfile,
                        format="%(asctime)s %(message)s")
    logging.getLogger('pika').setLevel(logging.WARNING)
    with setup_flask_app().app_context():
        main()


if __name__ == '__main__':
    cli()

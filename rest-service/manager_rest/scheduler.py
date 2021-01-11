import argparse
import logging
import os
import time
from datetime import datetime, timedelta
import dateutil.parser

from manager_rest import config
from manager_rest import manager_exceptions
from manager_rest.storage import db, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.flask_utils import setup_flask_app
from manager_rest.utils import set_current_tenant


def execute_workflow(schedule):
    rm = get_resource_manager()
    set_current_tenant(schedule.tenant)
    rm.execute_workflow(
        deployment_id=schedule.deployment.id,
        workflow_id=schedule.workflow_id,
        parameters=schedule.parameters,
        execution_creator=schedule.creator,
        execution_tenant=schedule.tenant,
        **(schedule.execution_arguments or {})
    )
    set_current_tenant(None)


def should_run(sched):
    if not sched.slip:
        return True
    slip = timedelta(seconds=sched.slip)
    next_occurrence = dateutil.parser.parse(sched.next_occurrence,
                                            ignoretz=True)
    return datetime.now() - next_occurrence < slip


def _update_next_occurrence(sched, current_next, new_next):
    table = models.ExecutionSchedule.__table__
    update_stmt = (
        table.update()
        .where(
            table.c._storage_id == sched._storage_id
        )
        .where(
            table.c.next_occurrence == current_next
        )
        .values(next_occurrence=new_next)
    )
    return db.session.execute(update_stmt)


def check_schedules():
    scheds = db.session.query(
        models.ExecutionSchedule
    ).filter(
        models.ExecutionSchedule.next_occurrence < datetime.now()
    ).with_for_update().all()
    if not scheds:
        db.session.rollback()
        return

    for sched in scheds:
        next_occurrence = sched.compute_next_occurrence()
        old_next_occurrence = sched.next_occurrence
        try:
            ret = _update_next_occurrence(
                sched, old_next_occurrence, next_occurrence)
            if ret.rowcount == 1:
                if should_run(sched):
                    logging.info('Running: %s', sched)
                    execute_workflow(sched)
                else:
                    logging.info('Not running: %s', sched)
        except manager_exceptions.ExistingRunningExecutionError:
            _update_next_occurrence(
                sched, next_occurrence, old_next_occurrence)
            logging.info('not running - already pending')

    db.session.commit()


def main():
    while True:
        check_schedules()
        time.sleep(60)


if __name__ == '__main__':
    if 'MANAGER_REST_CONFIG_PATH' not in os.environ:
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            "/opt/manager/cloudify-rest.conf"
        os.environ['MANAGER_REST_SECURITY_CONFIG_PATH'] = \
            "/opt/manager/rest-security.conf"
    config.instance.load_configuration()
    parser = argparse.ArgumentParser()

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with setup_flask_app().app_context():
        main()

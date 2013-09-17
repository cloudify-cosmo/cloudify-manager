__author__ = 'idanmo'

from cosmo.celery import celery
import tempfile
import os
from os import path
import json
from celery.utils.log import get_task_logger

DATA_FILE = path.join(tempfile.gettempdir(), "cloudmock.json")
RUNNING = "running"
NOT_RUNNING = "not_running"

logger = get_task_logger(__name__)


def _read_data_file():
    if not path.exists(DATA_FILE):
        return dict()
    with open(DATA_FILE, "r") as f:
        return json.loads(f.read())


def _save_data_file(machines):
    if path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    with open(DATA_FILE, "w") as f:
        f.write(json.dumps(machines))


@celery.task
def provision(__cloudify_id, **kwargs):
    logger.info("provisioning machine: " + __cloudify_id)
    machines = _read_data_file()
    if __cloudify_id in machines:
        raise RuntimeError("machine with id [{0}] already exists".format(__cloudify_id))
    machines[__cloudify_id] = NOT_RUNNING
    _save_data_file(machines)


@celery.task
def start(__cloudify_id, **kwargs):
    logger.info("starting machine: " + __cloudify_id)
    machines = _read_data_file()
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist".format(__cloudify_id))
    machines[__cloudify_id] = RUNNING
    _save_data_file(machines)


@celery.task
def stop(__cloudify_id, **kwargs):
    logger.info("stopping machine: " + __cloudify_id)
    machines = _read_data_file()
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist".format(__cloudify_id))
    machines[__cloudify_id] = NOT_RUNNING
    _save_data_file(machines)


@celery.task
def terminate(__cloudify_id, **kwargs):
    logger.info("terminating machine: " + __cloudify_id)
    machines = _read_data_file()
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist".format(__cloudify_id))
    del machines[__cloudify_id]
    _save_data_file(machines)


@celery.task
def get_machines(**kwargs):
    logger.info("getting machines")
    return _read_data_file()


import unittest


class CloudMockTest(unittest.TestCase):

    def setUp(self):
        if path.exists(DATA_FILE):
            os.remove(DATA_FILE)

    def test_provision(self):
        machine_id = "machine1"
        provision(__cloudify_id=machine_id)
        machines = get_machines()
        self.assertEqual(1, len(machines))
        self.assertTrue(machine_id in machines)
        self.assertEqual(NOT_RUNNING, machines[machine_id])

    def test_start(self):
        machine_id = "machine1"
        provision(__cloudify_id=machine_id)
        start(__cloudify_id=machine_id)
        machines = get_machines()
        self.assertEqual(1, len(machines))
        self.assertTrue(machine_id in machines)
        self.assertEqual(RUNNING, machines[machine_id])

    def test_stop(self):
        machine_id = "machine1"
        provision(__cloudify_id=machine_id)
        start(__cloudify_id=machine_id)
        stop(__cloudify_id=machine_id)
        machines = get_machines()
        self.assertEqual(1, len(machines))
        self.assertTrue(machine_id in machines)
        self.assertEqual(NOT_RUNNING, machines[machine_id])

    def test_terminate(self):
        machine_id = "machine1"
        provision(__cloudify_id=machine_id)
        terminate(__cloudify_id=machine_id)
        machines = get_machines()
        self.assertEqual(0, len(machines))


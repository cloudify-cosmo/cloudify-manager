########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'idanmo'

from cosmo.celery import celery
import os
from os import path
import json
from celery.utils.log import get_task_logger
from cosmo.events import set_reachable

RUNNING = "running"
NOT_RUNNING = "not_running"

logger = get_task_logger(__name__)
reachable = set_reachable
machines = {}

@celery.task
def provision(__cloudify_id, **kwargs):
    global machines
    logger.info("provisioning machine: " + __cloudify_id)
    if __cloudify_id in machines:
        raise RuntimeError("machine with id [{0}] already exists".format(__cloudify_id))
    machines[__cloudify_id] = NOT_RUNNING


@celery.task
def start(__cloudify_id, **kwargs):
    global machines
    logger.info("starting machine: " + __cloudify_id)
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist".format(__cloudify_id))
    machines[__cloudify_id] = RUNNING
    reachable(__cloudify_id)


@celery.task
def stop(__cloudify_id, **kwargs):
    global machines
    logger.info("stopping machine: " + __cloudify_id)
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist".format(__cloudify_id))
    machines[__cloudify_id] = NOT_RUNNING


@celery.task
def terminate(__cloudify_id, **kwargs):
    global machines
    logger.info("terminating machine: " + __cloudify_id)
    if __cloudify_id not in machines:
        raise RuntimeError("machine with id [{0}] does not exist".format(__cloudify_id))
    del machines[__cloudify_id]

@celery.task
def get_machines(**kwargs):
    logger.info("getting machines...")
    return machines

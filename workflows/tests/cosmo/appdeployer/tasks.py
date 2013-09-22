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
import subprocess
from celery.utils.log import get_task_logger


COSMO_JAR = os.environ.get('COSMO_JAR')

logger = get_task_logger(__name__)


@celery.task
def deploy(dsl, **kwargs):
    logger.info("deploying dsl: " + dsl)
    logger.info("cosmo jar: " + COSMO_JAR)
    command = [
        "java",
        "-jar",
        COSMO_JAR,
        "--dsl",
        dsl,
        "--non-interactive"
    ]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while True:
        line = p.stdout.readline().rstrip()
        if line == '':
            break
        logger.info(line)

    logger.info("dsl deployment has finished.")
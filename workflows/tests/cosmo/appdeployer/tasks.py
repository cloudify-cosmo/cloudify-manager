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
        dsl
    ]
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while True:
        line = p.stdout.readline().rstrip()
        if line == '':
            break
        logger.info(line)

    logger.info("dsl deployment has finished.")
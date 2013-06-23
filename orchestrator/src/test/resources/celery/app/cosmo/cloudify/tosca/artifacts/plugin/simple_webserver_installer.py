from __future__ import absolute_import

import sys
from cosmo.celery import celery

@celery.task
def install(**kwargs):
    sys.stdout.write('@@@@@@@@@@@@ provision\n')

@celery.task
def start(**kwargs):
    sys.stdout.write('@@@@@@@@@@@@ start\n')
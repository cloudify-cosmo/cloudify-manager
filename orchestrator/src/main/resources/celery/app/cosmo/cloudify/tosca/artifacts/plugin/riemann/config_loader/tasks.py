__author__ = 'dank'

from cosmo.celery import celery as celery
from celery.utils.log import get_task_logger
import os
import string
import signal
from configbuilder import build_riemann_config

logger = get_task_logger(__name__)

@celery.task
def reload_riemann_config(policies,
                          rules,
                          policies_events,
                          riemann_config_template,
                          riemann_config_path,
                          riemann_pid, 
                          **kwargs):
    
    new_riemann_config = build_riemann_config(riemann_config_template, policies, rules, policies_events)

    with open(riemann_config_path, 'w') as config:
        config.write(new_riemann_config)
    # causes riemann server to reload the configuration
    os.kill(int(riemann_pid), signal.SIGHUP)

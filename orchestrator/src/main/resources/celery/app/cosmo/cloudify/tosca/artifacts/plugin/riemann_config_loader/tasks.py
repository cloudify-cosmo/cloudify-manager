#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

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

    logger.debug("reloading riemann configuration")

    new_riemann_config = build_riemann_config(riemann_config_template, policies, rules, policies_events)

    with open(riemann_config_path, 'w') as config:
        config.write(new_riemann_config)
    # causes riemann server to reload the configuration
    os.kill(int(riemann_pid), signal.SIGHUP)

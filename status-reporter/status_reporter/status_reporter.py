#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import sys
import time
import json
import random
import logging
from logging.handlers import WatchedFileHandler

import yaml
import requests

from .constants import CONFIGURATION_PATH, STATUS_REPORTER


LOGFILE = '/var/log/cloudify/status-reporter/reporter.log'

logger = logging.getLogger(STATUS_REPORTER)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                  '[%(name)s] %(message)s',
                              datefmt='%d/%m/%Y %H:%M:%S')
file_handler = WatchedFileHandler(filename=LOGFILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def exception_handler(type, value, tb):
    logger.exception("Uncaught exception: {0}".format(str(value)))


# Install exception handler
sys.excepthook = exception_handler


class InitializationError(Exception):
    pass


class Reporter(object):
    def __init__(self, sampler, component_type):
        issues = []
        if not callable(sampler):
            issues.append('Reporter expected a callable sampler,'
                          ' got {0!r}..')
        self.status_sampler = sampler

        try:
            with open(CONFIGURATION_PATH) as f:
                self._config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append('Failed loading status reporter\'s '
                          'configuration with the following: {0}'.format(e))

        self._reporter_user_name = self._config.get('user_name', None)
        self._reporter_token = self._config.get('token', None)
        self._ca_path = self._config.get('ca_path', None)
        self._managers_ips = self._config.get('managers_ips', [])

        if not all([self._managers_ips,
                    self._reporter_token,
                    self._reporter_user_name
                    ]):
            invalid_conf_settings = {
                'Managers Ips': self._managers_ips,
                'Username': self._reporter_user_name,
                'Password token': self._reporter_token
            }
            issues.append('Please verify the reporter\'s config related to '
                          '{0} ..'.format(json.dumps(invalid_conf_settings,
                                                     indent=1)))

        if not self._ca_path or not os.path.exists(self._ca_path):
            issues.append('CA certificate was not found, '
                          'please verify the given location {0}'.format(
                           self._ca_path))

        self._current_reporting_freq = self._config.get('reporting_freq',
                                                        None)
        self._component_type = component_type
        if issues:
            raise InitializationError('Failed initialization of status '
                                      'reporter due to:\n {issues}'.format(
                                       issues='\n'.join(issues)))

    def _build_full_reporting_url(self, ip):
        return 'https://{0}/cluster_status/{1}'.format(ip,
                                                       self._component_type)

    def _build_report(self, status):
        return {'reporting_freq': self._current_reporting_freq,
                'report': status}

    def _update_managers_ips_list(self):
        for manager_ip in self._managers_ips:
            try:
                url = 'https://{}/managers'.format(manager_ip)
                response = requests.get(url,
                                        headers={'tenant': 'default_tenant'},
                                        verify=self._ca_path,
                                        auth=(self._reporter_user_name,
                                              self._reporter_token))
                managers_list = [dict.update(manager) for manager in
                                 response.json()['items']]
                self._managers_ips = [manager.get('public_ip') for manager in
                                      managers_list]
                return
            except Exception as e:
                logger.debug('Error had occurred while trying to update the '
                             'managers ips list: {}'.format(e))

    def _report(self):
        status = self.status_sampler()
        if not isinstance(status, dict):
            logger.error('Ignoring status: expected a report in dict format,'
                         ' got %s', status)
            return

        report = self._build_report(status)
        if report is None:
            return

        # If there is a malfunctioning manager,
        # let's try to avoid using the same manager always.
        random.shuffle(self._managers_ips)

        for manager_ip in self._managers_ips:
            try:
                requests.put(self._build_full_reporting_url(manager_ip),
                             data=report,
                             headers={'tenant': 'default_tenant'},
                             verify=self._ca_path,
                             auth=(self._reporter_user_name,
                                   self._reporter_token))
                return
            except Exception as e:
                logger.debug('Error had occurred while trying to report '
                             'status: {}'.format(e))
        logger.error('Could not find an active manager to '
                     'report the current status,'
                     ' tried %s', ','.join(self._managers_ips))
        self._update_managers_ips_list()

    def run(self):
        while True:
            self._report()
            time.sleep(self._current_reporting_freq)

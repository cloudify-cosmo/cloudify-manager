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
import datetime
from logging.handlers import WatchedFileHandler

from cloudify.constants import CLOUDIFY_API_AUTH_TOKEN_HEADER

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import SECURED_PROTOCOL

from .utils import update_yaml_file, read_from_yaml_file
from .constants import CONFIGURATION_PATH, STATUS_REPORTER, INTERNAL_REST_PORT


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
    def __init__(self, sampler, node_type):
        issues = []
        if not callable(sampler):
            issues.append('Reporter expected a callable sampler,'
                          ' got {0!r}..')
        self.status_sampler = sampler

        try:
            self._config = read_from_yaml_file(CONFIGURATION_PATH)
        except Exception as e:
            issues.append('Failed loading status reporter\'s '
                          'configuration with the following: {0}'.format(e))

        self._cloudify_user_name = self._config.get('user_name', None)
        self._token = self._config.get('token', None)
        self._ca_path = self._config.get('ca_path', None)
        self._managers_ips = self._config.get('managers_ips', [])

        if not all([self._managers_ips,
                    self._token,
                    self._cloudify_user_name
                    ]):
            invalid_conf_settings = {
                'Managers Ips': self._managers_ips,
                'Username': self._cloudify_user_name,
                'Password token': self._token
            }
            issues.append('Please verify the reporter\'s config related to '
                          '{0} ..'.format(json.dumps(invalid_conf_settings,
                                                     indent=1)))

        if not self._ca_path or not os.path.exists(self._ca_path):
            issues.append('CA certificate was not found, '
                          'please verify the given location {0}'.
                          format(self._ca_path))

        self._current_reporting_freq = self._config.get('reporting_freq',
                                                        None)
        self._node_type = node_type
        if issues:
            raise InitializationError('Failed initialization of status '
                                      'reporter due to:\n {issues}'.
                                      format(issues='\n'.join(issues)))
        self._node_id = self._config.get('node_id', None)
        self._reporter_credentials = {
            'username': self._cloudify_user_name,
            'token': self._token,
            'ca_path': self._ca_path
        }

    @staticmethod
    def _generate_timestamp():
        return datetime.datetime.utcnow().strftime('%Y%m%d%H%M+0000')

    def _build_report(self, status, services):
        return {'reporting_freq': self._current_reporting_freq,
                'timestamp': self._generate_timestamp(),
                'report': {'status': status,
                           'services': services}
                }

    def _update_managers_ips_list(self, client):
        response = client.manager.get_managers()
        self._managers_ips = [manager.get('public_ip') for manager in
                              response]
        update_yaml_file(CONFIGURATION_PATH, {
            'managers_ips': self._managers_ips
        })

    def _report_status(self, client, report):
        client.cluster_status.report_node_status(self._node_type,
                                                 self._node_id,
                                                 report)
        return True

    def _get_cloudify_http_client(self, host):
        return CloudifyClient(host=host,
                              username=self._cloudify_user_name,
                              headers={CLOUDIFY_API_AUTH_TOKEN_HEADER:
                                       self._token},
                              cert=self._ca_path,
                              tenant='default_tenant',
                              port=INTERNAL_REST_PORT,
                              protocol=SECURED_PROTOCOL
                              )

    def _report(self):
        status, services = self.status_sampler(self._reporter_credentials)
        if not isinstance(status, dict):
            logger.error('Ignoring status: expected a report in dict format,'
                         ' got %s', status)
            return

        report = self._build_report(status, services)
        if report is None:
            return

        # If there is a malfunctioning manager,
        # let's try to avoid using the same manager always.
        random.shuffle(self._managers_ips)
        reporting_result = False
        for manager_ip in self._managers_ips:
            try:
                client = self._get_cloudify_http_client(manager_ip)
                reporting_result = self._report_status(client, report)
                break
            except Exception as e:
                logger.debug('Error had occurred while trying to report '
                             'status: {0}'
                             .format(e))
        if reporting_result:
            self._update_managers_ips_list(client)
        else:
            logger.error('Could not find an active manager to '
                         'report the current status,'
                         ' tried %s', ','.join(self._managers_ips))

    def run(self):
        while True:
            self._report()
            time.sleep(self._current_reporting_freq)

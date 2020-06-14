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

from cloudify.cluster_status import ServiceStatus
from cloudify.constants import CLOUDIFY_API_AUTH_TOKEN_HEADER

from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.client import (SECURED_PROTOCOL,
                                         DEFAULT_PROTOCOL,
                                         DEFAULT_PORT)

from .utils import (
    update_yaml_file,
    read_from_yaml_file,
    get_systemd_services,
    get_supervisord_services
)
from .constants import CONFIGURATION_PATH, STATUS_REPORTER, INTERNAL_REST_PORT

LOGFILE = '/var/log/cloudify/status-reporter/reporter.log'
VALID_STATUS = [ServiceStatus.HEALTHY, ServiceStatus.FAIL,
                ServiceStatus.DEGRADED]

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


CA_DEFAULT_PATH = '/etc/cloudify/ssl/status_reporter_cert.pem'


class ServiceManagementMixin(object):
    def get_services(self, service_names):
        if self.service_management == 'supervisord':
            return get_supervisord_services(service_names)
        else:
            return get_systemd_services(service_names)


class Reporter(object):
    def __init__(self, node_type):
        issues = []

        try:
            self._config = read_from_yaml_file(CONFIGURATION_PATH)
        except Exception as e:
            issues.append('Failed loading status reporter\'s '
                          'configuration with the following: {0}'.format(e))

        self._cloudify_user_name = self._config.get('user_name')
        self._token = self._config.get('token')
        self._managers_ips = self._config.get('managers_ips', [])
        self._node_id = self._config.get('node_id')

        if not all([self._managers_ips,
                    self._token,
                    self._cloudify_user_name,
                    self._node_id
                    ]):
            invalid_conf_settings = {
                'Managers Ips': self._managers_ips,
                'Username': self._cloudify_user_name,
                'Cloudify password token': self._token,
                'Node id': self._node_id
            }
            issues.append('Please verify the reporter\'s config related to '
                          '{0} ..'.format(json.dumps(invalid_conf_settings,
                                                     indent=1)))
        self._ca_cert_valid = True
        if not os.path.isfile(CA_DEFAULT_PATH):
            issues.append('CA certificate was not found, '
                          'please verify the given location {0}'.
                          format(CA_DEFAULT_PATH))
            self._ca_cert_valid = False

        self._current_reporting_freq = self._config.get('reporting_freq')
        self._request_timeout = self._config.get('request_timeout')
        self._node_type = node_type
        if issues:
            raise InitializationError('Failed initialization of status '
                                      'reporter due to:\n {issues}'.
                                      format(issues='\n'.join(issues)))
        debug_level = self._config.get('log_level', logging.INFO)
        logger.setLevel(debug_level)

    @staticmethod
    def _generate_timestamp():
        return datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S+0000')

    def _build_report(self, status, services):
        return {'reporting_freq': self._current_reporting_freq,
                'timestamp': self._generate_timestamp(),
                'report': {'status': status,
                           'services': services}
                }

    def _update_managers_ips_list(self, client):
        try:
            response = client.manager.get_managers()
            self._managers_ips = [manager.get('private_ip') for manager in
                                  response]
            update_yaml_file(CONFIGURATION_PATH, {
                'managers_ips': self._managers_ips
            })
        except Exception as e:
            logger.error('Failed updating the managers ips list with the '
                         'following: {0}'.format(e))
            return

    def _report_status(self, client, report):
        client.cluster_status.report_node_status(self._node_type,
                                                 self._node_id,
                                                 report)
        return True

    def _get_cloudify_http_client(self, host):
        if self._ca_cert_valid:
            return CloudifyClient(host=host,
                                  username=self._cloudify_user_name,
                                  headers={CLOUDIFY_API_AUTH_TOKEN_HEADER:
                                           self._token},
                                  cert=CA_DEFAULT_PATH,
                                  tenant='default_tenant',
                                  port=INTERNAL_REST_PORT,
                                  protocol=SECURED_PROTOCOL,
                                  timeout=self._request_timeout
                                  )
        else:
            return CloudifyClient(host=host,
                                  username=self._cloudify_user_name,
                                  tenant='default_tenant',
                                  port=DEFAULT_PORT,
                                  protocol=DEFAULT_PROTOCOL,
                                  timeout=self._request_timeout
                                  )

    def _collect_status(self):
        raise NotImplementedError

    @staticmethod
    def _validate_status_format(status, services):
        if not isinstance(services, dict):
            logger.error('Ignoring status report: expected services in dict '
                         'format got {0}.'.format(services))
            return False

        if status not in VALID_STATUS:
            logger.error('Ignoring status: expected status to be `OK`, '
                         '`Fail`, or `Degraded`. got {0}.'.format(status))
            return False
        return True

    def _report(self):
        try:
            status, services = self._collect_status()
        except Exception as e:
            logger.error('Failed collecting node status, skipping sending the'
                         ' report. This is due to {0}'.format(e))
            return

        if not self._validate_status_format(status, services):
            return

        report = self._build_report(status, services)

        # If there is a malfunctioning manager,
        # let's try to avoid using the same manager always.
        random.shuffle(self._managers_ips)
        reporting_result = False
        for manager_ip in self._managers_ips:
            try:
                client = self._get_cloudify_http_client(manager_ip)
                reporting_result = self._report_status(client, report)
                logger.debug('Sent a status report to {0}:\n {1}'.format(
                    manager_ip,
                    json.dumps(report, indent=1)))
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

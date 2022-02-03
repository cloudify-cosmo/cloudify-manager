########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import time
import pytest
import retrying

from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.cluster_status import ServiceStatus, NodeServiceStatus

from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_general

SERVICES = {
    'Management Worker': 'cloudify-mgmtworker',
    'PostgreSQL': 'postgresql-9.5',
    'RabbitMQ': 'cloudify-rabbitmq',
    'Cloudify Composer': 'cloudify-composer',
    'Cloudify Console': 'cloudify-stage',
    'AMQP-Postgres': 'cloudify-amqp-postgres'
}


class TestManagerStatus(AgentlessTestCase):

    def test_status_response(self):
        # Force Prometheus to scrape the statuses
        self.restart_service('blackbox_exporter')
        self.restart_service('postgres_exporter')
        self.restart_service('node_exporter')
        time.sleep(1.5)
        self.execute_on_manager('bash -c "pkill -SIGHUP prometheus"')
        time.sleep(0.5)

        manager_status = self.client.manager.get_status()
        self.assertEqual(manager_status['status'], ServiceStatus.HEALTHY)

        # Services for all-in-one premium manager
        services = ['Webserver', 'Cloudify Console', 'AMQP-Postgres',
                    'Management Worker', 'Manager Rest-Service',
                    'Cloudify API', 'Cloudify Execution Scheduler',
                    'PostgreSQL', 'RabbitMQ', 'Cloudify Composer',
                    'Monitoring Service']
        self.assertEqual(
            len(manager_status['services']),
            len(services))
        statuses = [manager_status['services'][service]['status']
                    for service in services]
        self.assertNotIn(NodeServiceStatus.INACTIVE, statuses)

        services_status = list(manager_status['services'].values())
        remote_values = [service['is_remote'] for service in services_status]
        self.assertFalse(any(remote_values))

        existing_key = ['extra_info' in service for service in services_status]
        self.assertTrue(all(existing_key))

    def test_status_service_inactive(self):
        """One of the systemd services is down"""
        self._test_service_inactive('Management Worker')
        self._test_service_inactive('Cloudify Console')
        self._test_service_inactive('AMQP-Postgres')

    def test_status_optional_service_inactive(self):
        """One of the optional systemd services is down"""
        self._test_service_inactive('Cloudify Composer')

    def test_status_rabbit_inactive(self):
        self._test_service_inactive('RabbitMQ')

        # Verify RabbitMQ connection check failed when the service was down
        log_path = '/var/log/cloudify/rest/cloudify-rest-service.log'
        log_file = self.read_manager_file(log_path)
        self.assertIn('Broker check failed', log_file)

    def test_status_postgres_inactive(self):
        service_command = self.get_service_management_command()
        self._stop_service('PostgreSQL', service_command)
        error_msg = '500: Internal error occurred in manager REST server'
        self.assertRaisesRegex(
            CloudifyClientError,
            error_msg,
            self.client.manager.get_status
        )
        self._start_service('PostgreSQL', service_command)

    def _test_service_inactive(self, service):
        service_command = self.get_service_management_command()
        self._stop_service(service, service_command)
        status = self.client.manager.get_status()
        self.assertEqual(status['status'], ServiceStatus.FAIL)
        self.assertEqual(status['services'][service]['status'],
                         NodeServiceStatus.INACTIVE)

        self._start_service(service, service_command)

    def _stop_service(self, service, service_command):
        self.execute_on_manager(
            '{0} stop {1}'.format(
                service_command,
                SERVICES[service]
            )
        )
        time.sleep(1)

    def _start_service(self, service, service_command):
        self.execute_on_manager(
            '{0} start {1}'.format(
                service_command,
                SERVICES[service]
            )
        )
        self._verify_service_active(service)

    @retrying.retry(wait_fixed=1000, stop_max_attempt_number=10)
    def _verify_service_active(self, service):
        status = self.client.manager.get_status()
        self.assertEqual(status['status'], ServiceStatus.HEALTHY)
        self.assertEqual(status['services'][service]['status'],
                         NodeServiceStatus.ACTIVE)

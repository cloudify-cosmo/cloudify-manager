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

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase


ACTIVE_STATE = 'Active'
INACTIVE_STATE = 'Inactive'
HEALTHY_STATE = 'OK'
FAIL_STATE = 'FAIL'

SERVICES = {
    'Management Worker': 'cloudify-mgmtworker.service',
    'PostgreSQL': 'postgresql-9.5.service',
    'RabbitMQ': 'cloudify-rabbitmq.service',
    'Cloudify Composer': 'cloudify-composer.service',
    'Cloudify Console': 'cloudify-stage.service',
    'AMQP-Postgres': 'cloudify-amqp-postgres.service'
}


class TestManagerStatus(AgentlessTestCase):

    def test_status_response(self):
        manager_status = self.client.manager.get_status()
        self.assertEqual(manager_status['status'], HEALTHY_STATE)

        # Services for all-in-one premium manager
        services = ['Webserver', 'Cloudify Console', 'AMQP-Postgres',
                    'Management Worker', 'Manager Rest-Service', 'PostgreSQL',
                    'RabbitMQ', 'Cloudify Composer']
        self.assertEqual(len(manager_status['services'].keys()), len(services))
        statuses = [manager_status['services'][service]['status']
                    for service in services]
        self.assertNotIn(INACTIVE_STATE, statuses)

        services_status = manager_status['services'].values()
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
        log_file = self.read_manager_file(log_path)[-150:]
        self.assertIn('Broker check failed', log_file)

    def test_status_postgres_inactive(self):
        self._stop_service('PostgreSQL')
        error_msg = '500: Internal error occurred in manager REST server'
        self.assertRaisesRegexp(
            CloudifyClientError,
            error_msg,
            self.client.manager.get_status
        )

        self._start_service('PostgreSQL')

    def _stop_service(self, service):
        self.execute_on_manager('systemctl stop {}'.format(SERVICES[service]))
        time.sleep(1)

    def _test_service_inactive(self, service):
        self._stop_service(service)
        status = self.client.manager.get_status()
        self.assertEqual(status['status'], FAIL_STATE)
        self.assertEqual(status['services'][service]['status'], INACTIVE_STATE)

        self._start_service(service)

    def _start_service(self, service):
        self.execute_on_manager('systemctl start {}'.format(SERVICES[service]))
        status = self.client.manager.get_status()
        self.assertEqual(status['status'], HEALTHY_STATE)
        self.assertEqual(status['services'][service]['status'], ACTIVE_STATE)

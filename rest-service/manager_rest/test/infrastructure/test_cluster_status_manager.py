#########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

import unittest
from collections import namedtuple
from mock import patch

from manager_rest.cluster_status_manager import get_cluster_status
from manager_rest.storage.storage_manager import ListResult

PROMETHEUS_ALERTS = {
    'db2_down': {
        "data": {
            "alerts": [
                {
                    "activeAt": "2020-07-03T15:35:37.239973579Z",
                    "annotations": {
                        "summary": "Postgres Exporter is down"
                    },
                    "labels": {
                        "alertname": "PostgresExporterDown",
                        "instance": "172.22.0.6:53333",
                        "job": "federate_postgresql",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T15:35:37.239973579Z",
                    "annotations": {
                        "summary": "PostgreSQL cluster is degraded"
                    },
                    "labels": {
                        "alertname": "PostgreSQLClusterDegraded",
                        "job": "federate_postgresql",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "2e+00"
                }
            ]
        },
        "status": "success"
    },
    'db2_db3_down_phase1': {
        "data": {
            "alerts": [
                {
                    "activeAt": "2020-07-03T15:35:37.239973579Z",
                    "annotations": {
                        "summary": "Postgres Exporter is down"
                    },
                    "labels": {
                        "alertname": "PostgresExporterDown",
                        "instance": "172.22.0.6:53333",
                        "job": "federate_postgresql",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T15:37:07.239973579Z",
                    "annotations": {
                        "summary": "Postgres Exporter is down"
                    },
                    "labels": {
                        "alertname": "PostgresExporterDown",
                        "instance": "172.22.0.7:53333",
                        "job": "federate_postgresql",
                        "severity": "warning"
                    },
                    "state": "pending",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T15:35:37.239973579Z",
                    "annotations": {
                        "summary": "PostgreSQL cluster is degraded"
                    },
                    "labels": {
                        "alertname": "PostgreSQLClusterDegraded",
                        "job": "federate_postgresql",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "2e+00"
                }
            ]
        },
        "status": "success"
    },
    'db2_db3_down_phase2': {
        "data": {
            "alerts": [
                {
                    "activeAt": "2020-07-03T15:35:37.239973579Z",
                    "annotations": {
                        "summary": "Postgres Exporter is down"
                    },
                    "labels": {
                        "alertname": "PostgresExporterDown",
                        "instance": "172.22.0.6:53333",
                        "job": "federate_postgresql",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T15:37:07.239973579Z",
                    "annotations": {
                        "summary": "Postgres Exporter is down"
                    },
                    "labels": {
                        "alertname": "PostgresExporterDown",
                        "instance": "172.22.0.7:53333",
                        "job": "federate_postgresql",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T15:35:37.239973579Z",
                    "annotations": {
                        "summary": "PostgreSQL cluster is degraded"
                    },
                    "labels": {
                        "alertname": "PostgreSQLClusterDegraded",
                        "job": "federate_postgresql",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "1e+00"
                },
                {
                    "activeAt": "2020-07-03T15:37:22.239973579Z",
                    "annotations": {
                        "summary": "PostgreSQL database cluster is down"
                    },
                    "labels": {
                        "alertname": "PostgreSQLClusterDown",
                        "job": "federate_postgresql",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "1e+00"
                },
            ]
        },
        "status": "success"
    },
    'queue2_down_phase1': {
        "data": {
            "alerts": [
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ Prometheus plugin is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQPluginDown",
                        "instance": "172.22.0.8:53333",
                        "job": "federate_rabbitmq",
                        "severity": "warning"
                    },
                    "state": "pending",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ Prometheus plugin is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQPluginDown",
                        "instance": "172.22.0.9:53333",
                        "job": "federate_rabbitmq",
                        "severity": "warning"
                    },
                    "state": "pending",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ cluster is degraded"
                    },
                    "labels": {
                        "alertname": "RabbitMQClusterDegraded",
                        "job": "federate_rabbitmq",
                        "severity": "critical"
                    },
                    "state": "pending",
                    "value": "1e+00"
                }
            ]
        },
        "status": "success"
    },
    'queue2_down_phase2': {
        "data": {
            "alerts": [
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ Prometheus plugin is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQPluginDown",
                        "instance": "172.22.0.8:53333",
                        "job": "federate_rabbitmq",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ Prometheus plugin is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQPluginDown",
                        "instance": "172.22.0.9:53333",
                        "job": "federate_rabbitmq",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ cluster is degraded"
                    },
                    "labels": {
                        "alertname": "RabbitMQClusterDegraded",
                        "job": "federate_rabbitmq",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:15.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ cluster is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQClusterDown",
                        "job": "federate_rabbitmq",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "0e+00"
                }
            ]
        },
        "status": "success"
    },
    'db2_queue2_down': {
        "data": {
            "alerts": [
                {
                    "activeAt": "2020-07-03T16:37:22.239973579Z",
                    "annotations": {
                        "summary": "Postgres Exporter is down"
                    },
                    "labels": {
                        "alertname": "PostgresExporterDown",
                        "instance": "172.22.0.6:53333",
                        "job": "federate_postgresql",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:37:37.239973579Z",
                    "annotations": {
                        "summary": "PostgreSQL cluster is degraded"
                    },
                    "labels": {
                        "alertname": "PostgreSQLClusterDegraded",
                        "job": "federate_postgresql",
                        "severity": "critical"
                    },
                    "state": "pending",
                    "value": "2e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ Prometheus plugin is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQPluginDown",
                        "instance": "172.22.0.8:53333",
                        "job": "federate_rabbitmq",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ Prometheus plugin is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQPluginDown",
                        "instance": "172.22.0.9:53333",
                        "job": "federate_rabbitmq",
                        "severity": "warning"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:00.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ cluster is degraded"
                    },
                    "labels": {
                        "alertname": "RabbitMQClusterDegraded",
                        "job": "federate_rabbitmq",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "0e+00"
                },
                {
                    "activeAt": "2020-07-03T16:36:15.047177614Z",
                    "annotations": {
                        "summary": "RabbitMQ cluster is down"
                    },
                    "labels": {
                        "alertname": "RabbitMQClusterDown",
                        "job": "federate_rabbitmq",
                        "severity": "critical"
                    },
                    "state": "firing",
                    "value": "0e+00"
                }
            ]
        },
        "status": "success"
    },
}

Manager = namedtuple(
    'Manager',
    'is_external name public_ip private_ip version'
)
RabbitMQBroker = namedtuple(
    'RabbitMQBroker',
    'is_external name public_ip private_ip'
)
DBNodes = namedtuple(
    'DBNodes',
    'is_external name public_ip private_ip'
)


def _generate_cluster_structure():
    return {
        'db': ListResult(
            [
                DBNodes(
                    is_external=False, name='db1',
                    public_ip='172.22.0.5', private_ip='172.22.0.5'
                ),
                DBNodes(
                    is_external=False, name='db2',
                    public_ip='172.22.0.6', private_ip='172.22.0.6'
                ),
                DBNodes(
                    is_external=False, name='db3',
                    public_ip='172.22.0.7', private_ip='172.22.0.7'
                ),
            ],
            {}
        ),
        'broker': ListResult(
            [
                RabbitMQBroker(
                    is_external=False, name='queue1',
                    public_ip='172.22.0.8', private_ip='172.22.0.8'
                ),
                RabbitMQBroker(
                    is_external=False, name='queue2',
                    public_ip='172.22.0.9', private_ip='172.22.0.9'
                ),
            ],
            {}
        ),
        'manager': ListResult(
            [
                Manager(
                    is_external=False, name='manager1',
                    public_ip='172.22.0.3', private_ip='172.22.0.3',
                    version='5.1.0.dev1'
                ),
                Manager(
                    is_external=False, name='manager2',
                    public_ip='172.22.0.4', private_ip='172.22.0.4',
                    version='5.1.0.dev1'
                ),
            ],
            {}
        ),
    }


def _mocked_prometheus_alerts(key=None):
    return PROMETHEUS_ALERTS.get(key, {})


class ManagerConfigTestCase(unittest.TestCase):

    @patch('manager_rest.cluster_status_manager.'
           '_generate_cluster_status_structure')
    @patch('manager_rest.prometheus_client.alerts')
    def test_get_cluster_status_healthy(self, prometheus_alerts,
                                        structure_generator):
        prometheus_alerts.return_value = _mocked_prometheus_alerts()
        structure_generator.return_value = _generate_cluster_structure()
        cluster_status = get_cluster_status()
        prometheus_alerts.assert_called_once()
        structure_generator.assert_called_once()
        self.assertEqual('OK', cluster_status['status'])
        self.assertEqual(3, len(cluster_status['services']))
        # self.assertTrue(all(['OK' == s['status'] for _, s in
        #                      cluster_status['services'].items()]))
        for _, service in cluster_status['services'].items():
            self.assertEqual('OK', service['status'])
            for _, node in service['nodes'].items():
                self.assertEqual('OK', node['status'])


if __name__ == '__main__':
    unittest.main()

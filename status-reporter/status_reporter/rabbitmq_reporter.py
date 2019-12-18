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


from requests import get
from requests.exceptions import RequestException

from cloudify.cluster_status import (CloudifyNodeType, ServiceStatus,
                                     NodeServiceStatus)

from .status_reporter import Reporter, logger
from .constants import STATUS_REPORTER_CONFIG_KEY, EXTRA_INFO
from .utils import get_systemd_services, determine_node_status

NODE_STATUS = 'node_status'
CLUSTER_STATUS = 'cluster_status'
RABBITMQ_SERVICE_KEY = 'RabbitMQ'
HEALTH_CHECK_API = 'healthchecks/node'
CA_PATH = '/etc/cloudify/ssl/rabbitmq-ca.pem'
RABBITMQ_URL = 'https://localhost:15671/api/'
RABBITMQ_SERVICE = {'cloudify-rabbitmq.service': RABBITMQ_SERVICE_KEY}


class RabbitMQReporter(Reporter):
    def __init__(self):
        super(RabbitMQReporter, self).__init__(CloudifyNodeType.BROKER)

    def _collect_status(self):
        services, statuses = get_systemd_services(RABBITMQ_SERVICE)
        extra_config = self._config.get(STATUS_REPORTER_CONFIG_KEY)
        if self._is_rabbitmq_service_not_running(statuses) or not extra_config:
            return self._rabbitmq_status_failed(services)
        self._update_node_status(services, statuses, extra_config)
        self._update_cluster_status(services, statuses, extra_config)
        status = determine_node_status(statuses)
        return status, services

    @staticmethod
    def _is_rabbitmq_service_not_running(statuses):
        return NodeServiceStatus.INACTIVE in statuses

    def _update_cluster_status(self, services, statuses, config):
        cluster_status, cluster_extra_info = self._get_cluster_status(config)
        services[RABBITMQ_SERVICE_KEY][EXTRA_INFO][CLUSTER_STATUS] = \
            cluster_extra_info
        statuses.append(cluster_status)

    @staticmethod
    def _get_nodes_status(nodes_response):
        cluster_nodes = {}
        for node in nodes_response:
            cluster_nodes[node['name']] = (
                ServiceStatus.HEALTHY if node['running']
                else ServiceStatus.FAIL)

        return cluster_nodes

    def _get_cluster_status(self, config):
        nodes_response = self._query_rabbitmq(config, 'nodes')
        if not nodes_response:
            return NodeServiceStatus.INACTIVE, {}
        cluster_status = self._get_nodes_status(nodes_response.json())

        return NodeServiceStatus.ACTIVE, cluster_status

    def _update_node_status(self, services, statuses, config):
        node_status, node_extra_info = self._get_rabbitmq_node_status(config)
        services[RABBITMQ_SERVICE_KEY][EXTRA_INFO][NODE_STATUS] = \
            node_extra_info
        statuses.append(node_status)

    def _get_rabbitmq_node_status(self, config):
        response = self._query_rabbitmq(config, HEALTH_CHECK_API)
        if not response:
            return NodeServiceStatus.INACTIVE, {}

        response_body = response.json()
        if response.ok and response.json()['status'] == 'ok':
            return NodeServiceStatus.ACTIVE, response_body

        return NodeServiceStatus.INACTIVE, response_body

    @staticmethod
    def _query_rabbitmq(config, endpoint):
        rabbitmq_cred = (config['username'], config['password'])
        try:
            response = get(RABBITMQ_URL+endpoint, auth=rabbitmq_cred,
                           verify=CA_PATH)
        except RequestException as error:
            logger.error(
                'Failed getting RabbitMQ node status due to {0}'.format(error))
            return None

        return response

    @staticmethod
    def _rabbitmq_status_failed(services):
        services[RABBITMQ_SERVICE_KEY][EXTRA_INFO][NODE_STATUS] = {}
        services[RABBITMQ_SERVICE_KEY][EXTRA_INFO][CLUSTER_STATUS] = {}
        return ServiceStatus.FAIL, services


def main():
    reporter = RabbitMQReporter()
    reporter.run()

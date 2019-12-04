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

import json

from requests import get
from requests.exceptions import RequestException

from cloudify.utils import LocalCommandRunner
from cloudify.exceptions import CommandExecutionException
from cloudify.cluster_status import (CloudifyNodeType, ServiceStatus,
                                     NodeServiceStatus)

from .utils import (get_systemd_services, get_node_status, get_cloudify_config)
from .status_reporter import Reporter, logger

RABBITMQ_SERVICE_KEY = 'RabbitMQ'
CA_PATH = '/etc/cloudify/ssl/rabbitmq-ca.pem'
RABBITMQ_SERVICES = {'cloudify-rabbitmq.service': 'RabbitMQ'}
RABBITMQ_URL = 'https://localhost:15671/api/healthchecks/node'


class RabbitMQReporter(Reporter):
    def __init__(self):
        super(RabbitMQReporter, self).__init__(CloudifyNodeType.BROKER)

    def _collect_status(self):
        services, statuses = get_systemd_services(RABBITMQ_SERVICES)
        config = get_cloudify_config(logger)
        if self._rabbitmq_service_not_running(statuses) or not config:
            return self._rabbitmq_collect_status_failed(services)
        self._update_node_status(services, statuses, config)
        self._update_cluster_status(services, statuses, config)
        status = get_node_status(statuses)
        return status, services

    def _rabbitmq_service_not_running(self, statuses):
        return statuses[0] == NodeServiceStatus.INACTIVE

    def _update_cluster_status(self, services, statuses, config):
        cluster_status, cluster_extra_info = self._get_cluster_status(config)
        services[RABBITMQ_SERVICE_KEY]['extra_info']['cluster_status'] = \
            cluster_extra_info
        statuses.append(cluster_status)

    def _get_cluster_status(self, config):
        cluster_status_info = self._rabbitmqctl_cluster_status(config)
        if not cluster_status_info:
            return NodeServiceStatus.INACTIVE, {}

        return NodeServiceStatus.ACTIVE, cluster_status_info

    def _rabbitmqctl_cluster_status(self, config):
        cmd = self._get_cluster_status_cmd(config)
        runner = LocalCommandRunner()
        try:
            cluster_status_info = json.loads(runner.run(cmd).std_out)
        except CommandExecutionException as error:
            logger.error(
                'Failed getting RabbitMQ cluster-status due to '
                '{0}'.format(error))
            return None

        return cluster_status_info

    def _get_cluster_status_cmd(self, config):
        longnames = ('--longnames' if config['rabbitmq']['use_long_name']
                     else '')
        nodename = config['rabbitmq']['nodename']
        return ('sudo rabbitmqctl -n {nodename} {longnames} cluster_status '
                '--formatter json'.format(nodename=nodename,
                                          longnames=longnames))

    def _update_node_status(self, services, statuses, config):
        node_status, node_extra_info = self._get_rabbitmq_node_status(config)
        services[RABBITMQ_SERVICE_KEY]['extra_info']['node_status'] = \
            node_extra_info
        statuses.append(node_status)

    def _get_rabbitmq_node_status(self, config):
        detailed_status = self._query_rabbitmq(config)
        if not detailed_status:
            return NodeServiceStatus.INACTIVE, {}

        if 'error' in detailed_status:
            return NodeServiceStatus.INACTIVE, detailed_status

        return NodeServiceStatus.ACTIVE, detailed_status

    def _query_rabbitmq(self, config):
        rabbitmq_cred = (config['rabbitmq']['username'],
                         config['rabbitmq']['password'])
        try:
            response = get(RABBITMQ_URL, auth=rabbitmq_cred, verify=CA_PATH)
        except RequestException as error:
            logger.error(
                'Failed getting RabbitMQ node status due to {0}'.format(error))
            return None

        return response.json()

    def _rabbitmq_collect_status_failed(self, services):
        services['node_status'] = {}
        services['cluster_status'] = {}
        return ServiceStatus.FAIL, services


def main():
    reporter = RabbitMQReporter()
    reporter.run()

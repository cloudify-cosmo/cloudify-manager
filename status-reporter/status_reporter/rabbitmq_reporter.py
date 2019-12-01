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

import yaml
import json
import requests

from cloudify.utils import LocalCommandRunner
from cloudify.exceptions import CommandExecutionException
from cloudify.cluster_status import (CloudifyNodeType, ServiceStatus,
                                     NodeServiceStatus)

from .utils import get_systemd_services, get_node_status, get_service_status
from .status_reporter import Reporter, logger


class RabbitMQReporter(Reporter):
    def __init__(self):
        super(RabbitMQReporter, self).__init__(CloudifyNodeType.BROKER)

    def _collect_status(self):
        report = dict.fromkeys(['status', 'services'])
        rabbitmq_credentials = _get_rabbitmq_credentials()
        _check_rabbitmq_service(report)
        if report['services']['RabbitMQ']['status'] == \
                NodeServiceStatus.INACTIVE:  # rabbitmq service is down
            _fail_tests(report)
        else:
            _check_and_report_node_status(report, rabbitmq_credentials)
            _check_and_report_rabbitmq_cluster_status(report)
        _update_report_status(report)
        return report['status'], report['services']


def _get_rabbitmq_credentials():
    with open('/etc/cloudify/config.yaml') as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config['rabbitmq']['username'], config['rabbitmq']['password']


def _update_health_check_status(report, status):
    report['services']['RabbitMQ']['extra_info']['health_checks'] = status
    report['services']['RabbitMQ']['status'] = get_service_status([status])


def _check_and_report_node_status(report, rabbitmq_credentials):
    url = 'https://localhost:15671/api/healthchecks/node'
    try:
        response = requests.get(url, auth=rabbitmq_credentials, verify=False)
    except requests.exceptions.RequestException as e:
        logger.error(e)
        _update_health_check_status(report, ServiceStatus.FAIL)
        return
    if 'error' in response.json():
        status = ServiceStatus.FAIL
        logger.error('RabbitMQ health-check failed with: {0}'.format(
            response.content))
    else:
        status = ServiceStatus.HEALTHY
    _update_health_check_status(report, status)


def _update_cluster_status(report, cluster_status):
    report['services']['RabbitMQ']['extra_info']['cluster_status'] = \
        cluster_status
    if not cluster_status:
        report['services']['RabbitMQ']['status'] = get_service_status(
            [ServiceStatus.FAIL])


def _check_and_report_rabbitmq_cluster_status(report):
    cmd = 'sudo rabbitmqctl cluster_status --formatter json'
    runner = LocalCommandRunner()
    try:
        cluster_status = json.loads(runner.run(cmd).std_out)
    except CommandExecutionException as e:
        logger.error('RabbitMQ cluster-status failed with: {0}'.format(e))
        _update_cluster_status(report, {})
        return
    _update_cluster_status(report, cluster_status)


def _check_rabbitmq_service(report):
    service = {'cloudify-rabbitmq.service': 'RabbitMQ'}
    services, status = get_systemd_services(service)
    report['services'] = services


def _fail_tests(report):
    _update_health_check_status(report, ServiceStatus.FAIL)
    _update_cluster_status(report, {})


def _update_report_status(report):
    service_status = report['services']['RabbitMQ']['status']
    report['status'] = get_node_status([service_status])


def main():
    reporter = RabbitMQReporter()
    reporter.run()

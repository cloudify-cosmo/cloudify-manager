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
from cloudify.cluster_status import CloudifyNodeType, ServiceStatus

from .status_reporter import Reporter


def _get_rabbitmq_credentials():
    with open('/etc/cloudify/config.yaml') as config_file:
        config = yaml.load(config_file, yaml.Loader)
    return config['rabbitmq']['username'], config['rabbitmq']['password']


def _check_and_report_node_status(report, rabbitmq_credentials):
    url = 'https://localhost:15671/api/healthchecks/node'
    response = requests.get(url, auth=rabbitmq_credentials, verify=False)
    status = (ServiceStatus.HEALTHY if response.json()['status'] == 'ok' else
              ServiceStatus.FAIL)
    report['status'] = status


def _all_nodes_alive(cluster_status):
    return (sorted(cluster_status['nodes']['disc']) ==
            sorted(cluster_status['running_nodes']))


def _check_and_report_rabbitmq_cluster_status(report):
    cmd = 'rabbitmqctl cluster_status --formatter json'
    runner = LocalCommandRunner()
    try:
        cluster_status = json.loads(runner.run(cmd).std_out)
    except CommandExecutionException:
        # could not reach rabbitmq
        report['status'] = ServiceStatus.FAIL
        return
    report['services'] = cluster_status
    if report['status'] == ServiceStatus.HEALTHY:
        if not _all_nodes_alive(cluster_status):
            report['status'] = ServiceStatus.FAIL


def collect_status():
    report = dict.fromkeys(['status', 'services'])
    rabbitmq_credentials = _get_rabbitmq_credentials()
    _check_and_report_node_status(report, rabbitmq_credentials)
    _check_and_report_rabbitmq_cluster_status(report)
    return report


def main():
    reporter = Reporter(collect_status, CloudifyNodeType.BROKER)
    reporter.run()

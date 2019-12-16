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

from cloudify.cluster_status import CloudifyNodeType, NodeServiceStatus

from .status_reporter import Reporter, logger
from .constants import STATUS_REPORTER_CONFIG_KEY, EXTRA_INFO
from .utils import get_systemd_services, determine_node_status


PATRONI_URL = 'https://{private_ip}:8008'
CA_PATH = '/etc/etcd/ca.crt'
PATRONI_SERVICE_KEY = 'Patroni'
POSTGRES_SERVICES = {
    'patroni.service': PATRONI_SERVICE_KEY,
    'etcd.service': 'Etcd'
}


class PostgreSQLReporter(Reporter):
    def __init__(self):
        super(PostgreSQLReporter, self).__init__(CloudifyNodeType.DB)

    def _collect_status(self):
        services, systemd_statuses = get_systemd_services(POSTGRES_SERVICES)
        patroni_status, extra_info = self._get_patroni_status()
        services[PATRONI_SERVICE_KEY][EXTRA_INFO]['patroni_status'] = \
            extra_info
        services[PATRONI_SERVICE_KEY]['status'] = patroni_status
        status = determine_node_status(systemd_statuses + [patroni_status])
        return status, services

    def _get_patroni_status(self):
        extra_config = self._config.get(STATUS_REPORTER_CONFIG_KEY, {})
        private_ip = extra_config.get('private_ip')
        if not private_ip:
            return NodeServiceStatus.INACTIVE, {}

        detailed_status = self._query_patroni(private_ip)
        if not detailed_status:
            return NodeServiceStatus.INACTIVE, {}

        replications = detailed_status.get('replication', [])
        replications_state = [{'sync_state': rep['sync_state'],
                               'state': rep['state']}
                              for rep in replications]
        patroni_status = {
            'state': detailed_status['state'],
            'role': detailed_status['role'],
            'replications_state': replications_state
        }

        if patroni_status['state'] != 'running':
            return NodeServiceStatus.INACTIVE, patroni_status

        return NodeServiceStatus.ACTIVE, patroni_status

    def _query_patroni(self, private_ip):
        try:
            status_response = get(PATRONI_URL.format(private_ip=private_ip),
                                  verify='/etc/etcd/ca.crt')
        except RequestException as error:
            logger.error(
                "Failed getting Patroni's status, due to {0}".format(error)
            )
            return None

        return status_response.json()


def main():
    reporter = PostgreSQLReporter()
    reporter.run()

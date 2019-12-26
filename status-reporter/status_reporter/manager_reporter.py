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

from cloudify.cluster_status import CloudifyNodeType

from .status_reporter import Reporter
from .utils import read_from_yaml_file

CONFIG_PATH = '/etc/cloudify/config.yaml'


class ManagerReporter(Reporter):
    def __init__(self):
        config = read_from_yaml_file(CONFIG_PATH)
        super(ManagerReporter, self).__init__(
            CloudifyNodeType.MANAGER,
            config['constants']['ca_cert_path'])

    def _collect_status(self):
        client = self._get_cloudify_http_client('localhost')
        report = client.manager.get_status()
        return report['status'], report['services']


def main():
    reporter = ManagerReporter()
    reporter.run()

########
# Copyright (c) 2013-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from os.path import join
from integration_tests.framework import docker
from integration_tests.tests.constants import MANAGER_PYTHON
from integration_tests.tests.utils import (assert_messages_in_log,
                                           get_resource as resource)
from integration_tests.tests.utils import run_postgresql_command

COLLECTOR_SCRIPTS = ['collect_cloudify_uptime', 'collect_cloudify_usage']
SCRIPTS_DESTINATION_PATH = '/opt/cloudify/usage_collector'
LOG_PATH = '/var/log/cloudify/usage_collector'
LOG_FILE = 'usage_collector.log'


class TestUsageCollectorBase(object):
    def run_scripts_with_deployment(self, yaml_path, messages):
        deployment, _ = self.deploy_application(resource(yaml_path),
                                                timeout_seconds=120)
        self.run_collector_scripts_and_assert(messages)
        self.undeploy_application(deployment.id)
        self.clean_timestamps()

    def run_collector_scripts_and_assert(self, messages):
        docker.execute(self.env.container_id, 'mkdir -p {0}'.format(LOG_PATH))
        docker.execute(self.env.container_id, 'echo > {0}'.format(
            join(LOG_PATH, LOG_FILE)))
        for script in COLLECTOR_SCRIPTS:
            docker.execute(self.env.container_id, '{0} {1}.py'.format(
                MANAGER_PYTHON,
                join(SCRIPTS_DESTINATION_PATH, script))
            )
        assert_messages_in_log(self.env.container_id,
                               self.workdir,
                               messages,
                               join(LOG_PATH, LOG_FILE))

    def clean_timestamps(self):
        # this is necessary for forcing the collector scripts to actually run
        # in subsequent tests, despite not enough time passing since last run
        run_postgresql_command(
            self.env.container_id,
            "UPDATE usage_collector SET hourly_timestamp=0, daily_timestamp=0 "
            "WHERE id=0")

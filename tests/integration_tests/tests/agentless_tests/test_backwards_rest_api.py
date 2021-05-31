########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import json
import os
import subprocess
from functools import wraps

from integration_tests.framework import utils
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_rest


def skip_if_supervisord(test_method):
    @wraps(test_method)
    def wrapper(self):
        if self.env.service_management != 'supervisord':
            return test_method(self)
    return wrapper


class RestApiBackwardsCompatibilityTest(AgentlessTestCase):

    def setUp(self):
        super(RestApiBackwardsCompatibilityTest, self).setUp()

    @skip_if_supervisord
    def test_3_2_client(self):
        self._test_client(client_version='3.2',
                          url_version_postfix='')

    @skip_if_supervisord
    def test_3_3_1_client(self):
        self._test_client(client_version='3.3.1',
                          url_version_postfix='/api/v2')

    def _test_client(self, client_version, url_version_postfix):
        shell_script_path = resource('scripts/test_old_rest_client.sh')
        python_script_path = resource('scripts/test_old_rest_client.py')
        result_path = str(self.workdir / 'result.json')
        profile_context = utils.get_profile_context(self.env.container_id)

        env = os.environ.copy()
        env.update({
            'python_script_path': python_script_path,
            'client_version': client_version,
            'manager_ip': self.get_manager_ip(),
            'manager_user': profile_context['manager_username'],
            'manager_password': profile_context['manager_password'],
            'manager_tenant': profile_context['manager_tenant'],
            'url_version_postfix': url_version_postfix,
            'result_path': result_path
        })
        subprocess.check_call(shell_script_path,
                              shell=True,
                              cwd=str(self.workdir),
                              env=env)
        with open(result_path) as f:
            result = json.load(f)
        if result['failed']:
            self.fail('Failed to get manager status from old client. '
                      '[error={0}]'.format(result['details']))

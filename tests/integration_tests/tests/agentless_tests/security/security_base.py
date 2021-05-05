########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from contextlib import contextmanager

from cloudify_rest_client.exceptions import UserUnauthorizedError

from integration_tests.framework import utils
from integration_tests import AgentlessTestCase


class TestAuthenticationBase(AgentlessTestCase):
    @contextmanager
    def _login_client(self, **kwargs):
        self.logger.info('Logging in to client with %s', kwargs)
        client = self.client
        try:
            self.client = self.create_rest_client(**kwargs)
            yield
        finally:
            self.client = client

    def _assert_unauthorized(self, **kwargs):
        with self._login_client(**kwargs):
            self.assertRaises(
                UserUnauthorizedError,
                self.client.manager.get_status
            )

    def _assert_authorized(self, **kwargs):
        with self._login_client(**kwargs):
            self.client.manager.get_status()

########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from time import sleep
from os.path import join

from requests.exceptions import ConnectionError

from cloudify_rest_client.exceptions import CloudifyClientError

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import create_rest_client


class TestSsl(AgentlessTestCase):
    def test_ssl(self):
        local_cert_path = join(self.workdir, 'cert.pem')
        self.copy_file_from_manager(
            '/etc/cloudify/ssl/cloudify_external_cert.pem', local_cert_path)
        ssl_client = create_rest_client(
            rest_port='443', cert_path=local_cert_path)

        # only non-ssl client works
        self.assertEquals('SSL disabled', self.client.manager.ssl_status())
        self.assertRaises(ConnectionError, ssl_client.manager.ssl_status)

        # change to ssl - now only ssl client works
        self.client.manager.set_ssl(True)
        sleep(2)
        self.assertRaises(CloudifyClientError, self.client.manager.ssl_status)
        self.assertEquals('SSL enabled', ssl_client.manager.ssl_status())

        # change back to non-ssl - now only non-ssl client works
        ssl_client.manager.set_ssl(False)
        sleep(2)
        self.assertEquals('SSL disabled', self.client.manager.ssl_status())
        self.assertRaises(ConnectionError, ssl_client.manager.ssl_status)

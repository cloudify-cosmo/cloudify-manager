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

import unittest

from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.storage import models
from flask_login import current_user

try:
    import cloudify_premium
except ImportError:
    cloudify_premium = None


@attr(client_min_version=3.1, client_max_version=base_test.LATEST_API_VERSION)
@unittest.skipIf(not cloudify_premium,
                 reason='Endpoint not supported on community.')
class RabbitMQBrokersTest(base_test.BaseServerTestCase):
    def setUp(self):
        super(RabbitMQBrokersTest, self).setUp()
        self.cert = self.sm.put(models.Certificate(
            name='ca',
            value='cert-contents',
            updated_by=current_user
        ))
        self.broker = self.sm.put(models.RabbitMQBroker(
            name='broker',
            host='127.0.0.1',
            ca_cert=self.cert
        ))

    def test_get_list(self):
        """Check that listing brokers includes the cert value"""
        brokers = self.client.manager.get_brokers()
        self.assertEqual(len(brokers), 1)
        broker = brokers[0]
        self.assertEqual(broker.name, self.broker.name)
        self.assertEqual(broker.ca_cert_content, self.cert.value)

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

__author__ = 'idanmo'

from testenv import TestCase
from testenv import get_resource as resource
from testenv import deploy_application as deploy
from testenv import get_deployment_events


class TestDeploymentEvents(TestCase):

    def test_get_deployment_events(self):
        dsl_path = resource("dsl/basic.yaml")
        deploy(dsl_path)
        events = get_deployment_events('simple_web_server')
        self.assertEqual(0, events['firstEvent'])
        self.assertTrue(int(events['lastEvent']) > 0)


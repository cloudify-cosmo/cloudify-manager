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

from testenv import TestCase
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy
from testenv.utils import execute_workflow


class TestDeploymentModification(TestCase):

    def test_deployment_modification(self):
        dsl_path = resource("dsl/deployment_modification.yaml")
        deployment, _ = deploy(dsl_path)

        nodes = {
            'host': {
                'instances': 2
            }
        }
        execute_workflow('deployment_modification', deployment.id,
                         parameters={'nodes': nodes})

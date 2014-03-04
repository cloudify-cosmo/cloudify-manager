########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


__author__ = 'dan'

import time

from workflow_tests.testenv import TestCase
from workflow_tests.testenv import get_resource as resource
from workflow_tests.testenv import deploy_application as deploy
from workflow_tests.testenv import get_execution
from workflow_tests.testenv import cancel_execution


class BasicWorkflowsTest(TestCase):

    def test_cancel_execution(self):
        dsl_path = resource("dsl/cancel_workflow.yaml")
        _, execution_id = deploy(dsl_path,
                                 wait_for_execution=False)
        cancel_execution(execution_id)
        execution = get_execution(execution_id)
        endtime = time.time() + 10
        while execution.status not in ['terminated', 'failed'] and \
                time.time() < endtime:
            execution = get_execution(execution_id)
            time.sleep(1)

        self.assertEquals(execution.status, 'terminated')

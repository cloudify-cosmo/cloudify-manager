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

__author__ = 'ran'


from testenv import TestEnvironment
from testenv import TestEnvironmentScope
from testenv import create_new_rest_client
import unittest
import logging


class TestCase(unittest.TestCase):
    """
    A test case for cosmo workflow tests.
    """

    @classmethod
    def setUpClass(cls):
        TestEnvironment.create(TestEnvironmentScope.CLASS, False)

    @classmethod
    def tearDownClass(cls):
        TestEnvironment.destroy(TestEnvironmentScope.CLASS)

    def setUp(self):
        self.logger = logging.getLogger(self._testMethodName)
        self.logger.setLevel(logging.INFO)
        self.client = create_new_rest_client()
        TestEnvironment.clean_plugins_tempdir()

    def tearDown(self):
        TestEnvironment.restart_celery_operations_worker()
        TestEnvironment.restart_celery_workflows_worker()
        TestEnvironment.reset_elasticsearch_data()
        pass

    def create_celery_worker(self, queue):
        return TestEnvironment.create_celery_worker(queue)

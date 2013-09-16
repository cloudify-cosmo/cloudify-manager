#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

__author__ = 'elip'

import unittest
from test import update_cosmo_jar
from test import get_remote_runner, REMOTE_WORKING_DIR


class ValidateDSLTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.RUNNER = get_remote_runner()
        # dont use the retry mechanism for these tests
        cls.RUNNER.max_retries = 0
        # update_cosmo_jar(cls.RUNNER)

    def test_valid(self):

        self.RUNNER.run("{0}/cosmo.sh --dsl=/vagrant/test/python_webserver/python-webserver.yaml --validate"
                        .format(REMOTE_WORKING_DIR))

    def test_invalid(self):

        try:
            self.RUNNER.run("{0}/cosmo.sh --dsl=/vagrant/test/corrupted_dsl/dsl-with-invalid-plans1.yaml --validate"
                            .format(REMOTE_WORKING_DIR))
            self.fail("Expected validation exception but none occurred")
        except BaseException:
            pass


if __name__ == '__main__':
    unittest.main()
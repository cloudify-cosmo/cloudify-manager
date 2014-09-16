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
import os
import testenv

from cloudify.utils import id_generator
from testenv.constants import TOP_LEVEL_DIR
from testenv import TestEnvironment

"""
These methods are honored by nose.
They are executed at the package level. (Once for each package)

see http://nose.readthedocs.org/en/latest/writing_tests.html
"""


def setup_package():

    unique_name = 'WorkflowsTests-{0}'.format(id_generator(4))

    test_working_dir = os.path.join(
        TOP_LEVEL_DIR,
        unique_name
    )
    os.makedirs(test_working_dir)

    testenv.testenv_instance = TestEnvironment(test_working_dir)
    testenv.testenv_instance.create()


def teardown_package():
    testenv.testenv_instance.destroy()

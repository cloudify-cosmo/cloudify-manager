#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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


from os import path
from ConfigParser import ConfigParser

from nose.plugins import collect


def _extract_test_names(tests):
    return ['{0}:{1}.{2}'.format(test.test.__module__,
                                 type(test.test).__name__,
                                 test.test._testMethodName) for test in tests]


def _build_suites(tests, number_of_suites):
    number_of_tests = len(tests)
    number_of_suite_tests, remainder = divmod(number_of_tests,
                                              number_of_suites)
    offset = 0
    suites = []
    for i in range(number_of_suites):
        start = offset + i * number_of_suite_tests
        end = offset + i * number_of_suite_tests + number_of_suite_tests
        if remainder:
            offset += 1
            end += 1
            remainder -= 1
        suites.append(tests[start:end])
    return suites


def _write_config(suite, config_path):
    config = ConfigParser()
    section = 'nosetests'
    config.add_section(section)
    config.set(section, 'tests', ','.join(suite))
    with open(path.expanduser(config_path), 'w') as f:
        config.write(f)


class SuiteSplitter(collect.CollectOnly):

    name = 'suitesplitter'

    def __init__(self):
        super(SuiteSplitter, self).__init__()
        self.accumulated_tests = []
        self.suite_number = None
        self.suite_total = None
        self.suite_config_path = None

    def options(self, parser, env):
        super(collect.CollectOnly, self).options(parser, env=env)
        parser.add_option('--suite-total',  default=1, type=int)
        parser.add_option('--suite-number', default=0, type=int)
        parser.add_option('--suite-config-path', default='nose.cfy')

    def configure(self, options, conf):
        super(SuiteSplitter, self).configure(options, conf=conf)
        self.suite_total = options.suite_total
        self.suite_number = options.suite_number
        self.suite_config_path = options.suite_config_path

    def addSuccess(self, test):
        self.accumulated_tests.append(test)

    def finalize(self, result):
        tests = _extract_test_names(self.accumulated_tests)
        suites = _build_suites(tests, self.suite_total)
        assert tests == [test for suite in suites for test in suite]
        _write_config(suites[self.suite_number], self.suite_config_path)

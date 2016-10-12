########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
import sys
import logging
import datetime

from multiprocessing import Process
from os import path
from os.path import dirname, abspath, join

import sh
import yaml

from utils import sh_bake
from integration_tests import resources

nosetests = sh_bake(sh.nosetests)

logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('suite_runner')

log_file_path = os.path.join(os.path.expanduser('~'), 'suites_log_file.log')
file_handler = logging.FileHandler(log_file_path)
logger.addHandler(file_handler)

logging.getLogger('sh').setLevel(logging.INFO)


class SuiteRunner(object):

    def __init__(self, descriptor, reports_dir):
        self.groups = descriptor.split('#')
        resources_path = path.dirname(resources.__file__)
        self.integration_tests_dir = dirname(abspath(resources_path))
        self.reports_dir = reports_dir
        logger.info('SuiteRunner config: '
                    '[groups: {0}, tests_dir: {1}, reports_dir: {2}]'.
                    format(self.groups,
                           self.integration_tests_dir,
                           self.reports_dir))
        with open(join(
                self.integration_tests_dir, 'suites', 'suites.yaml')) as f:
            logger.debug('Loading suites_yaml..')
            self.suites_yaml = yaml.load(f.read())

        if not os.path.isdir(reports_dir):
            logger.debug('Creating logs dir {0}..'.format(reports_dir))
            os.makedirs(reports_dir)
        else:
            for report in os.listdir(self.reports_dir):
                old_report = join(self.reports_dir, report)
                logger.debug('Deleting old report {0}..'.format(old_report))
                os.remove(old_report)

    def run_all_groups(self):
        proc = []
        for group in self.groups:
            logger.debug('Creating process for suite {0}..'.format(group))
            p = Process(target=self.prepare_and_run_tests, args=(group, ))
            p.start()
            proc.append(p)

        for p in proc:
            p.join()

    def prepare_and_run_tests(self, group):
        logger.debug('Running suite {0}..'.format(group))
        tests = []
        testing_elements = group.split(',')
        for testing_element in testing_elements:
            if testing_element in self.suites_yaml:
                # The element is a suite. extracting tests from it.
                tests_in_suite = self.suites_yaml[testing_element]
                tests += tests_in_suite
            else:
                tests.append(testing_element)

        report_file = join(self.reports_dir,
                           '{0}-report.xml'.format(os.getpid()))
        logger.debug('Running tests: {0}, report: {1}'
                     .format(tests, report_file))

        os.chdir(join(self.integration_tests_dir, 'tests'))
        suites = ['agentless_tests/']
        nosetests(suites,
                  verbose=True,
                  nocapture=True,
                  with_xunit=bool(os.environ.get('JENKINS_JOB')),
                  xunit_file=report_file).wait()
        logger.info('Tests execution terminated successfully.')


def main():
    descriptor = sys.argv[1]
    if os.environ.get('CFY_LOGS_PATH') and not os.environ.get('JENKINS_JOB'):
        time = str(datetime.datetime.now()).split('.')[0]
        time = time.replace(' ', '_').replace('-', '').replace(':', '')
        os.environ['CFY_LOGS_PATH'] = os.path.join(
            os.path.expanduser(os.environ['CFY_LOGS_PATH']),
            '{0}_{1}'.format(time, descriptor))
    resources_path = path.dirname(resources.__file__)
    reports_dir = join(dirname(abspath(resources_path)), 'xunit-reports')
    if len(sys.argv) > 2:
        reports_dir = sys.argv[2]
    suites_runner = SuiteRunner(descriptor, reports_dir)
    suites_runner.run_all_groups()
    if os.environ.get('CFY_LOGS_PATH') and not os.environ.get('JENKINS_JOB'):
        logger.info('manager logs are available at {0}'.format(
            os.environ['CFY_LOGS_PATH']))

if __name__ == '__main__':
    main()

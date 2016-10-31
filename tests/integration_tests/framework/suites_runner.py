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
import tempfile
import datetime

from multiprocessing import Process
from os import path
from os.path import dirname, abspath, join
from shutil import copyfile

import sh
import yaml

from utils import sh_bake
from integration_tests import resources

nosetests = sh_bake(sh.nosetests)

logging.basicConfig(format='%(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger('suite_runner')

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

        tmp_dir = tempfile.mkdtemp()

        logger.debug('Copying tests files into tmp dir: {0}'.format(tmp_dir))
        os.chdir(join(self.integration_tests_dir, 'tests'))
        for test_file in tests:
            copyfile(test_file, os.path.join(tmp_dir,
                                             os.path.basename(test_file)))

        logger.debug('Copying __init__.py to tmp dir: {0}'.format(tmp_dir))
        copyfile(os.path.join(os.path.dirname(test_file), '__init__.py'),
                 os.path.join(tmp_dir, '__init__.py'))

        nosetests(tmp_dir,
                  verbose=True,
                  nocapture=True,
                  with_xunit=bool(os.environ.get('JENKINS_JOB')),
                  xunit_file=report_file).wait()


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
    if os.environ.get('CFY_LOGS_PATH'):
        logger.info('manager logs will be saved at {0}'.format(
            os.environ['CFY_LOGS_PATH']))
    else:
        logger.info('Saving manager logs is disabled by configuration, '
                    'to enable logs keeping, define "CFY_LOGS_PATH"')
    suites_runner.run_all_groups()


if __name__ == '__main__':
    main()

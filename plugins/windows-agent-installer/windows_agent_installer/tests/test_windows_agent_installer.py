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

__author__ = 'nir0s'

from packman.packman import do

import unittest
import os
from functools import wraps
from fabric.api import hide


TEST_DIR = '{0}/test_dir'.format(os.path.expanduser("~"))
TEST_FILE_NAME = 'test_file'
TEST_FILE = TEST_DIR + '/' + TEST_FILE_NAME
TEST_TAR_NAME = 'test_tar.tar.gz'
TEST_TAR = TEST_DIR + '/' + TEST_TAR_NAME
TEST_VENV = '{0}/test_venv'.format(os.path.expanduser("~"))
TEST_MODULE = 'xmltodict'
TEST_MOCK_MODULE = 'mockmodule'
TEST_TEMPLATES_DIR = 'packman/tests/templates'
TEST_TEMPLATE_FILE = 'mock_template.template'
MOCK_TEMPLATE_CONTENTS = 'TEST={{ test_template_parameter }}'

HIDE_LEVEL = 'everything'


def file(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        client = CommonHandler()
        client.rmdir(TEST_DIR, sudo=False)
        do('mkdir -p ' + TEST_DIR, sudo=False)
        do('touch ' + TEST_FILE, sudo=False)
        func(*args, **kwargs)
        client.rmdir(TEST_DIR, sudo=False)

    return execution_handler


def dir(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        client = CommonHandler()
        client.rmdir(TEST_DIR, sudo=False)
        do('mkdir -p ' + TEST_DIR, sudo=False)
        func(*args, **kwargs)
        client.rmdir(TEST_DIR, sudo=False)

    return execution_handler


def venv(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        client = PythonHandler()
        with hide(HIDE_LEVEL):
            client.pip('virtualenv==1.11.4', sudo=False)
            client.venv(TEST_VENV, sudo=False)
        func(*args, **kwargs)
        client.rmdir(TEST_VENV, sudo=False)

    return execution_handler


def mock_template(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        client = CommonHandler()

        template_file = TEST_TEMPLATES_DIR + '/' + TEST_TEMPLATE_FILE
        # do('touch ' + template_file, sudo=False)
        do('mkdir -p ' + TEST_TEMPLATES_DIR, sudo=False)
        with open(template_file, 'w+') as f:
            f.write(MOCK_TEMPLATE_CONTENTS)
        func(*args, **kwargs)
        client.rm(template_file, sudo=False)
    return execution_handler


class CommonHandlerTest(unittest.TestCase, CommonHandler):

    @file
    def test_find_in_dir_found(self):
        with hide(HIDE_LEVEL):
            outcome = self.find_in_dir(TEST_DIR, TEST_FILE_NAME, sudo=False)
        self.assertEquals(outcome, TEST_FILE)

    def test_find_in_dir_not_found(self):
        with hide(HIDE_LEVEL):
            outcome = self.find_in_dir(TEST_DIR, TEST_FILE, sudo=False)
        self.assertEquals(outcome, None)

    @dir
    def test_is_dir(self):
        outcome = self.is_dir(TEST_DIR)
        self.assertTrue(outcome)

    def test_is_not_dir(self):
        outcome = self.is_dir(TEST_DIR)
        self.assertFalse(outcome)

    @file
    def test_is_file(self):
        outcome = self.is_file(TEST_FILE)
        self.assertTrue(outcome)

    def test_is_not_file(self):
        outcome = self.is_file(TEST_FILE)
        self.assertFalse(outcome)

    # @file
    # def test_tar(self):
    #     outcome = self.tar(TEST_DIR, TEST_TAR, TEST_DIR)
    #     self.assertTrue(outcome)
    #     self.assertTrue(self.is_file(TEST_DIR + '/' + TEST_TAR_NAME))

    # def test_tar_no_dir(self):
    #     outcome = self.tar(chdir, output_file, input_path)
    #     self.assertFalse(outcome)

    # def test_untar(self):
    #     outcome = self.untar(chdir, input_file)
    #     self.assertTrue(outcome)
    #     self.assertTrue(is_file)

    # def test_untar_no_tar_file(self):
    #     outcome = self.untar(chdir, input_file)
    #     self.assertFalse(outcome)


class PythonHandlerTest(unittest.TestCase, PythonHandler, CommonHandler):

    def test_pip_existent_module(self):
        with hide(HIDE_LEVEL):
            outcome = self.pip(TEST_MODULE, sudo=False)
        self.assertTrue(outcome.succeeded)

    def test_pip_nonexistent_module(self):
        with hide(HIDE_LEVEL):
            outcome = self.pip(TEST_MOCK_MODULE, attempts=1, sudo=False)
        self.assertTrue(outcome.failed)

    @venv
    def test_venv(self):
        with hide(HIDE_LEVEL):
            self.pip('virtualenv==1.11.4', sudo=False)
        outcome = self.is_file('{0}/bin/python'.format(TEST_VENV))
        self.assertTrue(outcome)

    @venv
    def test_pip_existent_module_in_venv(self):
        with hide(HIDE_LEVEL):
            outcome = self.pip(TEST_MODULE, TEST_VENV, sudo=False)
        self.assertTrue(outcome.succeeded)

    @venv
    def test_pip_nonexistent_module_in_venv(self):
        with hide(HIDE_LEVEL):
            outcome = self.pip(TEST_MOCK_MODULE, TEST_VENV,
                               attempts=1, sudo=False)
        self.assertTrue(outcome.failed)

    def test_check_module_not_installed(self):
        with hide(HIDE_LEVEL):
            outcome = self.check_module_installed(TEST_MOCK_MODULE)
        self.assertFalse(outcome)

    def test_check_module_installed(self):
        # with hide(HIDE_LEVEL):
        self.pip(TEST_MODULE, sudo=False)
        outcome = self.check_module_installed(TEST_MODULE)
        self.assertTrue(outcome)


class DownloadsHandlerTest(unittest.TestCase, DownloadsHandler,
                           CommonHandler):

    @dir
    def test_wget_file_to_dir(self):
        with hide(HIDE_LEVEL):
            self.wget('www.google.com', dir=TEST_DIR, sudo=False)
        outcome = self.is_file('{0}/index.html'.format(TEST_DIR))
        self.assertTrue(outcome)

    @dir
    def test_wget_file_to_file(self):
        with hide(HIDE_LEVEL):
            self.wget('www.google.com', file=TEST_FILE, sudo=False)
        outcome = self.is_file(TEST_FILE)
        self.assertTrue(outcome)

    def test_wget_nonexistent_url(self):
        with hide(HIDE_LEVEL):
            outcome = self.wget('www.google.comd', dir=TEST_DIR, sudo=False)
        self.assertTrue(outcome.failed)


class TemplateHandlerTest(unittest.TestCase, TemplateHandler,
                          CommonHandler):

    @file
    @mock_template
    def test_template_creation(self):
        component = {'test_template_parameter': 'test_template_output'}
        template_file = TEST_TEMPLATE_FILE
        self.generate_from_template(component, TEST_FILE, template_file,
                                    templates=TEST_TEMPLATES_DIR)
        with open(TEST_FILE, 'r') as f:
            self.assertIn('test_template_output', f.read())

    @mock_template
    def test_template_creation_template_file_missing(self):
        component = {'test_template_parameter': 'test_template_output'}
        template_file = 'mock_template'
        try:
            self.generate_from_template(component, TEST_FILE, template_file,
                                        templates=TEST_TEMPLATES_DIR)
        except PackagerError as ex:
            self.assertEqual(str(ex), 'template file missing')

    @mock_template
    def test_template_creation_template_dir_missing(self):
        component = {'test_template_parameter': 'test_template_output'}
        template_file = TEST_TEMPLATE_FILE
        try:
            self.generate_from_template(component, TEST_FILE, template_file,
                                        templates='')
        except PackagerError as ex:
            self.assertEqual(str(ex), 'template dir missing')

    @file
    @mock_template
    def test_template_creation_invalid_component_dict(self):
        component = ''
        template_file = TEST_TEMPLATE_FILE
        try:
            self.generate_from_template(component, TEST_FILE, template_file,
                                        templates=TEST_TEMPLATES_DIR)
        except PackagerError as ex:
            self.assertEqual(str(ex), 'component must be of type dict')

    @file
    @mock_template
    def test_template_creation_template_file_not_string(self):
        component = {'test_template_parameter': 'test_template_output'}
        template_file = False
        try:
            self.generate_from_template(component, TEST_FILE, template_file,
                                        templates=TEST_TEMPLATES_DIR)
        except PackagerError as ex:
            self.assertEqual(str(ex), 'template_file must be of type string')

    @file
    @mock_template
    def test_template_creation_template_dir_not_string(self):
        component = {'test_template_parameter': 'test_template_output'}
        template_file = TEST_TEMPLATE_FILE
        try:
            self.generate_from_template(component, TEST_FILE, template_file,
                                        templates=False)
        except PackagerError as ex:
            self.assertEqual(str(ex), 'template_dir must be of type string')

    @dir
    @mock_template
    def test_config_generation_from_config_dir(self):
        config_file = TEST_TEMPLATE_FILE
        component = {
            "sources_path": TEST_DIR,
            "test_template_parameter": "test_template_parameter",
            "config_templates": {
                "__config_dir": {
                    "files": TEST_TEMPLATES_DIR,
                    "config_dir": "config",
                }
            }
        }
        self.generate_configs(component, sudo=False)
        with open('{}/{}/{}'.format(component['sources_path'],
                  component['config_templates']['__config_dir']['config_dir'],
                  config_file), 'r') as f:
            self.assertIn(component['test_template_parameter'], f.read())

    @dir
    @mock_template
    def test_config_generation_from_template_dir(self):
        config_file = TEST_TEMPLATE_FILE
        component = {
            "sources_path": TEST_DIR,
            "test_template_parameter": "test_template_output",
            "config_templates": {
                "__template_dir": {
                    "templates": TEST_TEMPLATES_DIR,
                    "config_dir": "config",
                }
            }
        }
        self.generate_configs(component, sudo=False)
        with open('{}/{}/{}'.format(component['sources_path'],
                  component['config_templates']['__template_dir']['config_dir'],  # NOQA
                  config_file.split('.')[0:-1][0]), 'r') as f:
            self.assertIn(component['test_template_parameter'], f.read())

    @dir
    @mock_template
    def test_config_generation_from_template_file(self):
        config_file = TEST_TEMPLATE_FILE
        component = {
            "sources_path": TEST_DIR,
            "test_template_parameter": "test_template_output",
            "config_templates": {
                "__template_file": {
                    "template": TEST_TEMPLATES_DIR + '/' + config_file,
                    "output_file": config_file.split('.')[0:-1][0],
                    "config_dir": "config",
                }
            }
        }
        self.generate_configs(component, sudo=False)
        with open('{}/{}/{}'.format(component['sources_path'],
                  component['config_templates']['__template_file']['config_dir'],  # NOQA
                  config_file.split('.')[0:-1][0]), 'r') as f:
            self.assertIn(component['test_template_parameter'], f.read())


class TestBaseMethods(unittest.TestCase):

    def test_do(self):
        with hide(HIDE_LEVEL):
            outcome = do('uname -n', sudo=False)
        self.assertTrue(outcome.succeeded)

    def test_do_failure(self):
        with hide(HIDE_LEVEL):
            outcome = do('illegal operation', attempts=1, sudo=False)
        self.assertTrue(outcome.failed)

    def test_do_zero_attempts(self):
        try:
            with hide(HIDE_LEVEL):
                do('uname -n', attempts=0, sudo=False)
        except RuntimeError as ex:
            self.assertEqual(str(ex), 'attempts must be at least 1')

    def test_do_zero_sleeper(self):
        try:
            with hide(HIDE_LEVEL):
                do('uname -n', sleep_time=0, sudo=False)
        except RuntimeError as ex:
            self.assertEqual(str(ex), 'sleep_time must be larger than 0')

    # @dir
    # def test_pack(self):
    #     template_file = TEST_TEMPLATE_FILE
    #     config_file = TEST_TEMPLATE_FILE
    #     component = {
    #         "name": "test_package",
    #         "version": "3.0.0",
    #         "depends": [
    #             'test_dependency',
    #         ],
    #         "package_path": TEST_DIR,
    #         "sources_path": TEST_DIR + '/test_sources_dir',
    #         "src_package_type": "dir",
    #         "dst_package_type": "deb",
    #         # "bootstrap_script": 'bootstrap_script.sh',
    #         # "bootstrap_template": template_file,
    #         "config_templates": {
    #             "__template_file": {
    #                 "template": TEST_TEMPLATES_DIR + '/' + config_file,
    #                 "output_file": config_file.split('.')[0:-1][0],
    #                 "config_dir": "config",
    #             },
    #             # "__template_dir": {
    #             #     "templates": TEST_TEMPLATES_DIR,
    #             #     "config_dir": "config",
    #             # },
    #             # "__config_dir": {
    #             #     "files": TEST_TEMPLATES_DIR,
    #             #     "config_dir": "config",
    #             # }
    #         }
    #     }
    #     pack(component)

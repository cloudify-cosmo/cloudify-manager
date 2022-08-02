#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from typing import Any, Dict
from manager_rest.test import base_test

from dsl_parser.exceptions import DSLParsingException


class ValidateVersionTestCase(base_test.BaseServerTestCase):

    def test_validate_version_explicit_false(self):
        self._test(validate_version=False,
                   validation_passed=True)

    def test_validate_version_implicit(self):
        self._test(validate_version=None,
                   validation_passed=False)

    def test_validate_version_explicit_true(self):
        self._test(validate_version=True,
                   validation_passed=False)

    def _test(self, validate_version, validation_passed):
        self._create_context(validate_version=validate_version)
        assert validation_passed == self._upload_blueprint()

    def _create_context(self, validate_version):
        context: Dict[str, Any] = {'cloudify': {}}
        if validate_version is not None:
            context['cloudify'][
                'validate_definitions_version'] = validate_version
        self.client.manager.create_context('context', context)

    def _upload_blueprint(self):
        file_name = 'blueprint_validate_definitions_version.yaml'
        try:
            self.put_blueprint(blueprint_file_name=file_name)
            return True
        except DSLParsingException:
            return False

    @classmethod
    def initialize_provider_context(cls):
        # each test in this class creates its own provider context
        pass

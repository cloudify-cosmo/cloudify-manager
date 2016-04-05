#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import os

from nose.plugins.attrib import attr

from manager_rest.test import base_test
from manager_rest.test.base_test import BaseServerTestCase
from manager_rest.utils import read_json_file, write_dict_to_json_file


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class UtilsTests(BaseServerTestCase):

    def test_read_write_json_file(self):
        test_dict = {'test': 1, 'dict': 2}
        tmp_file_path = os.path.join(self.tmpdir, 'tmp_dict.json')
        write_dict_to_json_file(tmp_file_path, test_dict)
        read_dict = read_json_file(tmp_file_path)
        self.assertEqual(test_dict, read_dict)

        test_dict = {'test': 3, 'new': 2}
        write_dict_to_json_file(tmp_file_path, test_dict)
        read_dict = read_json_file(tmp_file_path)
        self.assertEqual(3, read_dict['test'])
        self.assertEqual(test_dict, read_dict)

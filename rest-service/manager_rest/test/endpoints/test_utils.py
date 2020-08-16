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

from manager_rest.test.attribute import attr

from manager_rest.utils import read_json_file, write_dict_to_json_file
from manager_rest.test import base_test


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class TestUtils(base_test.BaseServerTestCase):

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


def generate_progress_func(total_size, buffer_size=8192):
    """Generate a function that helps test upload/download progress

    :param total_size: Total size of the file to upload/download
    :param buffer_size: Size of chunk
    :return: A function that receives 2 ints - number of bytes read so far,
    and the total size in bytes
    """
    # Wrap the integer in a list, to allow mutating it inside the inner func
    iteration = [0]
    max_iterations = total_size // buffer_size

    def print_progress(read, total):
        i = iteration[0]
        assert total == total_size

        expected_read_value = buffer_size * (i + 1)
        if i < max_iterations:
            assert read == expected_read_value
        else:
            assert read == total_size

        iteration[0] += 1

    return print_progress

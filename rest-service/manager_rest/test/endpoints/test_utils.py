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

from mock import patch
from nose.plugins.attrib import attr

from manager_rest.utils import read_json_file, write_dict_to_json_file
from manager_rest.utils import plugin_installable_on_current_platform
from manager_rest.test import base_test
from manager_rest.storage import models


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

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_plugin_installable_on_current_platform(self):
        def create_plugin(supported_platform=None,
                          distribution=None,
                          distribution_release=None):
            mock_data = {k: 'stub' for k in models.Plugin.resource_fields}
            mock_data.pop('tenant_name')
            if supported_platform:
                mock_data['supported_platform'] = supported_platform
            if distribution:
                mock_data['distribution'] = distribution
            if distribution_release:
                mock_data['distribution_release'] = distribution_release
            return models.Plugin(**mock_data)

        plugin = create_plugin()
        self.assertFalse(plugin_installable_on_current_platform(plugin))

        plugin = create_plugin(supported_platform='any')
        self.assertTrue(plugin_installable_on_current_platform(plugin))

        platform = 'platform1'
        dist = 'dist1'
        rel = 'rel1'

        def mock_linux_dist(full_distribution_name):
            return dist, '', rel

        def mock_get_platform():
            return platform

        with patch('platform.linux_distribution', mock_linux_dist):
            with patch('wagon.utils.get_platform', mock_get_platform):
                plugin = create_plugin(supported_platform=platform)
                self.assertFalse(
                    plugin_installable_on_current_platform(plugin))

                plugin = create_plugin(distribution=dist,
                                       distribution_release=rel)
                self.assertFalse(
                    plugin_installable_on_current_platform(plugin))

                plugin = create_plugin(supported_platform=platform,
                                       distribution=dist,
                                       distribution_release=rel)
                self.assertTrue(
                    plugin_installable_on_current_platform(plugin))


def generate_progress_func(total_size, assert_equal,
                           assert_almost_equal, buffer_size=8192):
    """
    Generate a function that helps to predictably test upload/download progress
    :param total_size: Total size of the file to upload/download
    :param assert_equal: The unittest.TestCase assertEqual method
    :param assert_almost_equal: The unittest.TestCase assertAlmostEqual method
    :param buffer_size: Size of chunk
    :return: A function that receives 2 ints - number of bytes read so far,
    and the total size in bytes
    """
    # Wrap the integer in a list, to allow mutating it inside the inner func
    iteration = [0]
    max_iterations = total_size / buffer_size

    def print_progress(read, total):
        i = iteration[0]
        # tar.gz sizes are a bit inconsistent - tend to be a few bytes off
        assert_almost_equal(total, total_size, delta=5)

        expected_read_value = buffer_size * (i + 1)
        if i < max_iterations:
            assert_equal(read, expected_read_value)
        else:
            # On the last iteration, we face the same problem
            assert_almost_equal(read, total_size, delta=5)

        iteration[0] += 1

    return print_progress

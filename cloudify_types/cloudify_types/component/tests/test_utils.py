# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import tempfile

from cloudify_types import utils
from .base_test_suite import ComponentTestBase


class TestUtils(ComponentTestBase):

    @staticmethod
    def generate_temp_file():
        fd, destination = tempfile.mkstemp()
        os.close(fd)
        return destination

    @staticmethod
    def cleaning_up_files(files_paths):
        for path in files_paths:
            os.remove(path)

    def test_zip_files(self):
        test_file = self.generate_temp_file()
        zip_file = utils.zip_files([test_file])
        self.assertTrue(zip_file)
        self.cleaning_up_files([zip_file, test_file])

    def test_get_local_path_local(self):
        test_file = self.generate_temp_file()
        copy_file = utils.get_local_path(test_file, create_temp=True)
        self.assertTrue(copy_file)
        self.cleaning_up_files([copy_file, test_file])

    def test_get_local_path_https(self):
        copy_file = utils.get_local_path(
            "http://www.getcloudify.org/spec/cloudify/4.5/types.yaml",
            create_temp=True)
        self.assertTrue(copy_file)
        self.cleaning_up_files([copy_file])

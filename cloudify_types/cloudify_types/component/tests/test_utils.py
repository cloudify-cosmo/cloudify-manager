# Copyright (c) 2017-2018 Cloudify Platform Ltd. All rights reserved
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

import tempfile
import os

from cloudify.state import current_ctx
from .base import DeploymentProxyTestBase
import cloudify_types.component.utils as utils


class TestUtils(DeploymentProxyTestBase):

    def test_zip_files(self):
        _ctx = self.get_mock_ctx(__name__)
        current_ctx.set(_ctx)
        fd, destination = tempfile.mkstemp()
        os.close(fd)
        zip_file = utils.zip_files([destination])
        self.assertTrue(zip_file)
        os.remove(zip_file)
        os.remove(destination)

    def test_get_local_path_local(self):
        _ctx = self.get_mock_ctx(__name__)
        current_ctx.set(_ctx)
        fd, destination = tempfile.mkstemp()
        os.close(fd)
        copy_file = utils.get_local_path(destination, create_temp=True)
        self.assertTrue(copy_file)
        os.remove(copy_file)
        os.remove(destination)

    def test_get_local_path_https(self):
        _ctx = self.get_mock_ctx(__name__)
        current_ctx.set(_ctx)
        copy_file = utils.get_local_path(
            "http://www.getcloudify.org/spec/cloudify/4.5/types.yaml",
            create_temp=True)
        self.assertTrue(copy_file)
        os.remove(copy_file)

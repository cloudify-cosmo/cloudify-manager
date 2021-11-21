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

from manager_rest.test import base_test


class AppTestCase(base_test.BaseServerTestCase):
    """Test the basic HTTP interface, app-wide error handling
    """
    def test_get_root_404(self):
        """GET / returns a 404.

        Check that the app can handle requests that couldn't be routed,
        doesn't break with a 500.
        """
        resp = self.app.get('/')
        self.assertEqual(404, resp.status_code)

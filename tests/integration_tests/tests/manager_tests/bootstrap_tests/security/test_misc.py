########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from .test_base import TestSecuredRestBase, TestSSLRestBase


class TestBasicSecuredRest(TestSecuredRestBase):

    def test_basic_secured_rest(self):
        self.bootstrap_secured_manager()
        self.test_hello_world()


class TestSecuredRestSslGeneratedCertificateAgentVerify(TestSSLRestBase):

    def test_ssl_generated_certificate_agent_verify(self):
        self.bootstrap_secured_manager()
        self.test_hello_world()

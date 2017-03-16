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

from .test_base import TestSSLRestBase


class CertsLocationTest(TestSSLRestBase):

    def test_certs_location(self):
        rel_path = 'cloudify/ssl/cloudify_internal_cert.pem'
        self.bootstrap_secured_manager()
        deployment = self.test_hello_world(
            modify_blueprint_func=None,
            skip_uninstall=True)
        self.read_manager_file(os.path.join('/etc', rel_path))
        hosts = [
            host for host in self.client.node_instances.list()
            if host.node_id == 'vm' and host.deployment_id == deployment.id
            ]
        self.assertEquals(1, len(hosts))
        host_name = hosts[0].id
        path = os.path.join(os.environ['HOME'], host_name, rel_path)
        self.read_host_file(path, node_id='vm', deployment_id=deployment.id)

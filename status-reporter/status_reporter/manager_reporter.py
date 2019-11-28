#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

from cloudify_rest_client import CloudifyClient
from cloudify.cluster_status import CloudifyNodeType
from cloudify.constants import CLOUDIFY_API_AUTH_TOKEN_HEADER
from cloudify_rest_client.client import SECURED_PROTOCOL

from .status_reporter import Reporter
from .constants import INTERNAL_REST_PORT


def collect_status(reporter_credentials):
    client = CloudifyClient(host='localhost',
                            username=reporter_credentials.get('username'),
                            headers={CLOUDIFY_API_AUTH_TOKEN_HEADER:
                                     reporter_credentials.get('token')},
                            cert=reporter_credentials.get('ca_path'),
                            tenant='default_tenant',
                            port=INTERNAL_REST_PORT,
                            protocol=SECURED_PROTOCOL
                            )
    return client.manager.get_status()


def main():
    reporter = Reporter(collect_status, CloudifyNodeType.MANAGER)
    reporter.run()

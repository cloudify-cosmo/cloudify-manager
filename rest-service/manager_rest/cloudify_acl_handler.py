#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from flask_securest.acl_handlers.abstract_acl_handler import AbstractACLHandler

SECURITY_CTX_USER = 'user'


class CloudifyACLHandler(AbstractACLHandler):

    def __init__(self):
        pass

    def get_acl(self, security_context):
        return ['ALLOW#{0}#ALL'.format(security_context[SECURITY_CTX_USER])]

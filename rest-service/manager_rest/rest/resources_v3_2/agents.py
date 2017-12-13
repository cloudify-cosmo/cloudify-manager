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

from manager_rest.rest import rest_decorators
from manager_rest.storage.models import Execution
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize


class AgentsUpgrade(SecuredResource):
    @rest_decorators.exceptions_handled
    @authorize('agents_upgrade', allow_all_tenants=True)
    @rest_decorators.marshal_with(Execution)
    @rest_decorators.all_tenants
    def get(self, all_tenants=None, **kwargs):
        """
        Upgrade agents
        """
        pass

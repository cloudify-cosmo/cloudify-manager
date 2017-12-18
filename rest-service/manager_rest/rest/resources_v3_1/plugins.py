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

from manager_rest.storage import models
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager
from manager_rest.storage.models_states import AvailabilityState
from manager_rest.rest import (resources_v2,
                               rest_decorators,
                               rest_utils)


class PluginsSetGlobal(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('resource_set_global')
    @rest_decorators.marshal_with(models.Plugin)
    def patch(self, plugin_id):
        """
        Set the plugin's availability to global
        """
        return get_resource_manager().set_availability(
            models.Plugin,
            plugin_id,
            AvailabilityState.GLOBAL
        )


class PluginsSetAvailability(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('resource_set_availability')
    @rest_decorators.marshal_with(models.Plugin)
    def patch(self, plugin_id):
        """
        Set the plugin's availability
        """
        availability = rest_utils.get_availability_parameter()
        return get_resource_manager().set_availability(models.Plugin,
                                                       plugin_id,
                                                       availability)


class Plugins(resources_v2.Plugins):
    @rest_decorators.exceptions_handled
    @authorize('plugin_upload')
    @rest_decorators.marshal_with(models.Plugin)
    def post(self, **kwargs):
        """
        Upload a plugin
        """
        availability = rest_utils.get_availability_parameter(
            optional=True,
            is_argument=True,
            valid_values=AvailabilityState.STATES
        )
        with rest_utils.skip_nested_marshalling():
            return super(Plugins, self).post(availability=availability)

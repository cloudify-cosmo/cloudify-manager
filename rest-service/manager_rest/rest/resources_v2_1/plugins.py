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

import sys

from flask_restful_swagger import swagger

from manager_rest import manager_exceptions
from manager_rest.storage.models import Plugin
from manager_rest.resource_manager import get_resource_manager
from manager_rest.rest import rest_utils, resources_v2, rest_decorators


class PluginsId(resources_v2.PluginsId):

    @swagger.operation(
        responseClass=Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @rest_decorators.exceptions_handled
    @rest_decorators.marshal_with(Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        request_dict = rest_utils.get_json_and_verify_params()
        force = rest_utils.verify_and_convert_bool(
            'force', request_dict.get('force', False)
        )
        try:
            return get_resource_manager().remove_plugin(plugin_id=plugin_id,
                                                        force=force)
        except manager_exceptions.ManagerException:
            raise
        except manager_exceptions.ExecutionTimeout:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationTimeout(
                'Timed out during plugin un-installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb
        except Exception:
            tp, ex, tb = sys.exc_info()
            raise manager_exceptions.PluginInstallationError(
                'Failed during plugin un-installation. ({0}: {1})'
                .format(tp.__name__, ex)), None, tb

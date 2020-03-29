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

from cloudify._compat import reraise

from manager_rest.storage import models
from manager_rest import manager_exceptions
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager

from .. import rest_decorators, resources_v2
from ..rest_utils import verify_and_convert_bool, get_json_and_verify_params


class PluginsId(resources_v2.PluginsId):

    @swagger.operation(
        responseClass=models.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @authorize('plugin_delete')
    @rest_decorators.marshal_with(models.Plugin)
    def delete(self, plugin_id, **kwargs):
        """
        Delete plugin by ID
        """
        request_dict = get_json_and_verify_params()
        force = verify_and_convert_bool(
            'force', request_dict.get('force', False)
        )
        try:
            return get_resource_manager().remove_plugin(plugin_id=plugin_id,
                                                        force=force)
        except manager_exceptions.ManagerException:
            raise
        except manager_exceptions.ExecutionTimeout:
            tp, ex, tb = sys.exc_info()
            reraise(
                manager_exceptions.PluginInstallationTimeout,
                manager_exceptions.PluginInstallationTimeout(
                    'Timed out during plugin un-installation. '
                    '({0}: {1})'.format(tp.__name__, ex)
                ),
                tb)
        except Exception:
            tp, ex, tb = sys.exc_info()
            reraise(
                manager_exceptions.PluginInstallationError,
                manager_exceptions.PluginInstallationError(
                    'Failed during plugin un-installation. '
                    '({0}: {1})'.format(tp.__name__, ex)
                ),
                tb)

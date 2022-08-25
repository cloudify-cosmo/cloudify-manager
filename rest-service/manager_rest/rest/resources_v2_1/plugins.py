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

import pydantic
from flask import request
from typing import Optional

from manager_rest.rest import swagger
from manager_rest.storage import models
from manager_rest.security.authorization import authorize
from manager_rest.resource_manager import get_resource_manager

from .. import resources_v2


class _PluginDeleteArgs(pydantic.BaseModel):
    force: Optional[bool] = False


class PluginsId(resources_v2.PluginsId):

    @swagger.operation(
        responseClass=models.Plugin,
        nickname="deleteById",
        notes="deletes a plugin according to its ID."
    )
    @authorize('plugin_delete')
    def delete(self, plugin_id, **kwargs):
        """Delete plugin by ID"""
        params = _PluginDeleteArgs.parse_obj(request.json)
        get_resource_manager().remove_plugin(
            plugin_id=plugin_id,
            force=params.force,
        )
        return "", 204

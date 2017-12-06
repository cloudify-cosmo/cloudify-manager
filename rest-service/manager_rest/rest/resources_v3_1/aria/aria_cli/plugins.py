#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

from ..... import upload_manager
from .... import rest_decorators
from . import base


class ARIAPlugin(base.BaseARIAEndpoints):
    def post(self, plugin_id, **kwargs):
        """
        Upload (and install) a plugin
        """
        service_template_manager = \
            upload_manager.UploadARIAPluginManager(self.core)
        return service_template_manager.receive_uploaded_data(
            data_id=plugin_id)

    @rest_decorators.exceptions_handled
    def get(self, plugin_id, **kwargs):
        """
        Get Plugin by id
        """
        return self.model.plugin.get(plugin_id).to_dict(), 200


class ARIAPlugins(base.BaseARIAEndpoints):
    def get(
            self,
            _include=None,
            filters=None,
            pagination=None,
            sort=None,
            **kwargs
    ):
        """
        Get a Plugin list
        """
        return self._respond_list(
            self.model.plugin.list(
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                **kwargs
            )
        )

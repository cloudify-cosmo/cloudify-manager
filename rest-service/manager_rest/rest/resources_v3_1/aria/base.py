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
from tempfile import mkdtemp

from flask_restful import Resource

from aria import core, install_aria_extensions
from aria import application_resource_storage
from aria import storage
from aria.orchestrator import plugin

from manager_rest.storage import aria_model

install_aria_extensions(strict=False)


class BaseARIAEndpoints(Resource):
    def __init__(self, *args, **kwargs):
        super(BaseARIAEndpoints, self).__init__(*args, **kwargs)
        self._tmpdir = mkdtemp()
        self._model = None
        self._resource = None
        self._plugin_manager = None
        self._core = None

    @property
    def core(self):
        if self._core is None:
            self._core = core.Core(
                self.model, self.resource, self.plugin_manager)
        return self._core

    @property
    def model(self):
        if self._model is None:
            self._model = aria_model.get_model_storage()
        return self._model

    @property
    def resource(self):
        if self._resource is None:
            self._resource = application_resource_storage(
                storage.filesystem_rapi.FileSystemResourceAPI,
                api_kwargs=dict(directory=self._tmpdir)
            )
        return self._resource

    @property
    def plugin_manager(self):
        if self._plugin_manager is None:
            self._plugin_manager = plugin.PluginManager(
                self.model, self._tmpdir)
        return self._plugin_manager

    @staticmethod
    def _respond_list(list_):
        return {
            'items': [i.to_dict(
                set(i.fields()) - {
                    'created_at',
                    'updated_at',
                    'started_at',
                    'ended_at'}
            )
                      for i in list_],
            'metadata': list_.metadata
        }

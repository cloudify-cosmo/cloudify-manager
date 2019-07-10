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

from flask_restful.inputs import boolean
from flask_restful_swagger import swagger
from flask_restful.reqparse import Argument

from cloudify.models_states import VisibilityState
from cloudify.plugins.install_utils import remove_status_prefix

from manager_rest.security import SecuredResource
from manager_rest.plugins_update.constants import PHASES
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.utils import create_filter_params_list_description
from manager_rest.plugins_update.manager import get_plugins_updates_manager
from manager_rest.rest import (resources_v2,
                               resources_v2_1,
                               rest_decorators,
                               rest_utils)


class PluginsSetGlobal(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('resource_set_global')
    @rest_decorators.marshal_with(models.Plugin)
    def patch(self, plugin_id):
        """
        Set the plugin's visibility to global
        """
        return get_resource_manager().set_visibility(
            models.Plugin,
            plugin_id,
            VisibilityState.GLOBAL
        )


class PluginsSetVisibility(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('resource_set_visibility')
    @rest_decorators.marshal_with(models.Plugin)
    def patch(self, plugin_id):
        """
        Set the plugin's visibility
        """
        visibility = rest_utils.get_visibility_parameter()
        return get_resource_manager().set_visibility(models.Plugin,
                                                     plugin_id,
                                                     visibility)


class Plugins(resources_v2.Plugins):
    @rest_decorators.exceptions_handled
    @authorize('plugin_upload')
    @rest_decorators.marshal_with(models.Plugin)
    def post(self, **kwargs):
        """
        Upload a plugin
        """

        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            is_argument=True,
            valid_values=VisibilityState.STATES
        )
        with rest_utils.skip_nested_marshalling():
            return super(Plugins, self).post(visibility=visibility)


class PluginsUpdate(SecuredResource):

    @rest_decorators.exceptions_handled
    @authorize('plugins_update_create')
    @rest_decorators.marshal_with(models.PluginsUpdate)
    def post(self, id, phase):
        """
        Supports two stages of a plugin update.
        Phases:
            1. (PHASES.INITIAL) Creates a temporary blueprint and executes a
            deployment update (will update only the plugins) for all the
            deployments of the given blueprint.
            2. (PHASES.FINAL) Updates the original blueprint plan and deletes
            the temp one.

        :param id: the blueprint ID to update it's deployments' plugins if
        phase == PHASES.INITIAL, otherwise (phase == PHASES.FINAL) the plugin
        update ID.
        :param phase: either PHASES.INITIAL or PHASES.FINAL (internal).
        """
        if phase == PHASES.INITIAL:
            args = rest_utils.get_args_and_verify_arguments([
                Argument('force', type=boolean, required=False, default=False)
            ])
            return get_plugins_updates_manager().initiate_plugins_update(
                blueprint_id=id, force=args.get('force'))
        elif phase == PHASES.FINAL:
            return get_plugins_updates_manager().finalize(
                plugins_update_id=id)


class PluginsUpdateId(SecuredResource):
    @swagger.operation(
        responseClass=models.PluginsUpdate,
        nickname="PluginsUpdate",
        notes='Return a single plugins update',
        parameters=create_filter_params_list_description(
            models.PluginsUpdate.response_fields, 'plugins update')
    )
    @rest_decorators.exceptions_handled
    @authorize('plugins_update_get')
    @rest_decorators.marshal_with(models.PluginsUpdate)
    def get(self, update_id, _include=None):
        """Get a plugins update by id"""
        return get_storage_manager().get(
            models.PluginsUpdate, update_id, include=_include)


class PluginsUpdates(SecuredResource):
    @swagger.operation(
        responseClass='List[{0}]'.format(models.PluginsUpdate.__name__),
        nickname="listPluginsUpdates",
        notes='Returns a list of plugins updates',
        parameters=create_filter_params_list_description(
            models.PluginsUpdate.response_fields,
            'plugins updates'
        )
    )
    @rest_decorators.exceptions_handled
    @authorize('plugins_update_list')
    @rest_decorators.marshal_with(models.PluginsUpdate)
    @rest_decorators.create_filters(models.PluginsUpdate)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.PluginsUpdate)
    @rest_decorators.search('id')
    def get(self,
            _include=None,
            filters=None,
            pagination=None,
            sort=None,
            search=None,
            **_):
        """List plugins updates"""
        plugins_update = \
            get_plugins_updates_manager().list_plugins_updates(
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                substr_filters=search
            )
        return plugins_update


class PluginsId(resources_v2_1.PluginsId):

    @rest_decorators.exceptions_handled
    @authorize('plugin_upload')
    @rest_decorators.marshal_with(models.Plugin)
    def put(self, plugin_id, **kwargs):
        """
        For internal use - updates the plugin's installation status.'
        This method is called from the PluginInstaller after the plugin
        installation has ended.
        """

        sm = get_storage_manager()
        plugin = sm.get(models.Plugin, plugin_id)
        plugin = remove_status_prefix(plugin)
        if plugin:
            return sm.update(plugin)

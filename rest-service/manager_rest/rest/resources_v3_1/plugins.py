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

from flask_restful_swagger import swagger
from werkzeug.exceptions import BadRequest

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.plugins_update.constants import PHASES
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager
from manager_rest.resource_manager import get_resource_manager
from manager_rest.utils import create_filter_params_list_description
from manager_rest.plugins_update.constants import (PLUGIN_NAMES,
                                                   TO_LATEST,
                                                   ALL_TO_LATEST,
                                                   TO_MINOR,
                                                   ALL_TO_MINOR,
                                                   MAPPING,
                                                   FORCE,
                                                   AUTO_CORRECT_TYPES,
                                                   REEVALUATE_ACTIVE_STATUSES,)
from manager_rest.plugins_update.manager import get_plugins_updates_manager
from manager_rest.rest import (resources_v2,
                               resources_v2_1,
                               rest_decorators,
                               rest_utils)


class PluginsSetGlobal(SecuredResource):

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

    @authorize('plugins_update_create')
    @rest_decorators.marshal_with(models.PluginsUpdate)
    def post(self, id, phase, **kwargs):
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
        try:
            filters = rest_utils.get_json_and_verify_params({
                PLUGIN_NAMES: {'type': list, 'optional': True},
                ALL_TO_LATEST: {'type': bool, 'optional': True},
                TO_LATEST: {'type': list, 'optional': True},
                ALL_TO_MINOR: {'type': bool, 'optional': True},
                TO_MINOR: {'type': list, 'optional': True},
                MAPPING: {'type': dict, 'optional': True},
                FORCE: {'type': bool, 'optional': True},
                AUTO_CORRECT_TYPES: {'type': bool, 'optional': True},
                REEVALUATE_ACTIVE_STATUSES: {'type': bool, 'optional': True},
            })
        except BadRequest:
            filters = {}
        auto_correct_types = filters.pop(AUTO_CORRECT_TYPES, False)
        reevaluate_active_statuses = filters.pop(REEVALUATE_ACTIVE_STATUSES,
                                                 False)
        if phase == PHASES.INITIAL:
            return get_plugins_updates_manager().initiate_plugins_update(
                blueprint_id=id, filters=filters,
                auto_correct_types=auto_correct_types,
                reevaluate_active_statuses=reevaluate_active_statuses)
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
    @authorize('plugin_upload')
    @rest_decorators.marshal_with(models.Plugin)
    def post(self, plugin_id, **kwargs):
        """Force plugin installation on the given managers or agents.

        This method is for internal use only.
        """
        sm = get_storage_manager()
        action_dict = rest_utils.get_json_and_verify_params({
            'action': {'type': text_type},
        })
        plugin = sm.get(models.Plugin, plugin_id)
        if action_dict.get('action') == 'install':
            install_dict = rest_utils.get_json_and_verify_params({
                'managers': {'type': list, 'optional': True},
                'agents': {'type': list, 'optional': True},
            })
            get_resource_manager().install_plugin(
                plugin,
                manager_names=install_dict.get('managers'),
                agent_names=install_dict.get('agents'),
            )
            return get_resource_manager().install_plugin(plugin)
        else:
            raise manager_exceptions.UnknownAction(action_dict.get('action'))

    @authorize('plugin_upload')
    def put(self, plugin_id, **kwargs):
        """Update the plugin, specifically the installation state.

        Only updating the state is supported right now.
        This method is for internal use only.
        """
        request_dict = rest_utils.get_json_and_verify_params({
            'agent': {'type': text_type, 'optional': True},
            'manager': {'type': text_type, 'optional': True},
            'state': {'type': text_type},
            'error': {'type': text_type, 'optional': True},
        })
        agent_name = request_dict.get('agent')
        manager_name = request_dict.get('manager')
        if agent_name and manager_name:
            raise manager_exceptions.ConflictError(
                'Expected agent or manager, got both')
        elif not agent_name and not manager_name:
            raise manager_exceptions.ConflictError(
                'Expected agent or manager, got none')

        sm = get_storage_manager()
        try:
            plugin = sm.get(models.Plugin, plugin_id)
            # render response under the try/except - avoid marshal_with
            # in case the plugin was removed concurrently
            response = plugin.to_response()

            agent, manager = None, None
            if agent_name:
                agent = sm.get(
                    models.Agent, None, filters={'name': agent_name})
            elif manager_name:
                manager = sm.get(
                    models.Manager, None, filters={'hostname': manager_name})

            # response = plugin.to_response()
            get_resource_manager().set_plugin_state(
                plugin=plugin, manager=manager, agent=agent,
                state=request_dict['state'], error=request_dict.get('error'))
        except manager_exceptions.SQLStorageException as e:
            # plugin was most likely deleted concurrently - refetch it
            # to confirm: the .get() will throw a 404
            plugin = sm.get(models.Plugin, plugin_id)
            # ...if it doesn't throw, something is seriously wrong!
            raise RuntimeError('Unknown error setting plugin {0} state: {1}'
                               .format(plugin_id, e))
        return response

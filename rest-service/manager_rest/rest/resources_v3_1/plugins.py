from flask_restful_swagger import swagger
from werkzeug.exceptions import BadRequest

from cloudify._compat import text_type
from cloudify.models_states import VisibilityState

from manager_rest import manager_exceptions
from manager_rest.security import SecuredResource
from manager_rest.plugins_update.constants import PHASES
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
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
            args = rest_utils.get_json_and_verify_params({
                PLUGIN_NAMES: {'type': list, 'optional': True},
                ALL_TO_LATEST: {'type': bool, 'optional': True},
                TO_LATEST: {'type': list, 'optional': True},
                ALL_TO_MINOR: {'type': bool, 'optional': True},
                TO_MINOR: {'type': list, 'optional': True},
                MAPPING: {'type': dict, 'optional': True},
                FORCE: {'type': bool, 'optional': True},
                AUTO_CORRECT_TYPES: {'type': bool, 'optional': True},
                REEVALUATE_ACTIVE_STATUSES: {'type': bool, 'optional': True},
                'all_tenants': {'type': bool, 'optional': True},
                'creator': {'type': text_type, 'optional': True},
                'created_at': {'type': text_type, 'optional': True},
                'update_id': {'type': text_type, 'optional': True},
                'execution_id': {'type': text_type, 'optional': True},
                'state': {'type': text_type, 'optional': True},
                'affected_deployments': {'type': list, 'optional': True},
                'temp_blueprint_id': {'type': text_type, 'optional': True},
            })
        except BadRequest:
            args = {}

        filter_args = [
            PLUGIN_NAMES, MAPPING, FORCE,
            ALL_TO_LATEST, TO_LATEST, ALL_TO_MINOR, TO_MINOR,
        ]

        filters = {arg: value for arg, value in args.items()
                   if arg in filter_args}

        auto_correct_types = args.get(AUTO_CORRECT_TYPES, False)
        reevaluate_active_statuses = args.get(REEVALUATE_ACTIVE_STATUSES,
                                              False)

        update_manager = get_plugins_updates_manager()

        if any(arg in args for arg in ['creator', 'created_at', 'update_id',
                                       'execution_id', 'state',
                                       'affected_deployments',
                                       'temp_blueprint_id']):
            check_user_action_allowed('set_plugin_update_details')
            if not args.get('state'):
                raise manager_exceptions.BadParametersError(
                    'State must be supplied when overriding plugin update '
                    'settings.'
                )

            created_at = None
            if args.get('created_at'):
                check_user_action_allowed('set_timestamp', None, True)
                created_at = rest_utils.parse_datetime_string(
                    args['created_at'])

            plugins_update = update_manager.stage_plugin_update(
                blueprint=update_manager.sm.get(models.Blueprint, id),
                forced=args.get('force', False),
                update_id=args.get('update_id'),
                created_at=created_at,
                all_tenants=args.get('all_tennats', False),
            )

            if args.get('creator'):
                check_user_action_allowed('set_owner', None, True)
                plugins_update.creator = rest_utils.valid_user(
                    args['creator'])

            plugins_update.state = args['state']
            if args.get('execution_id'):
                plugins_update._execution_fk = update_manager.sm.get(
                    models.Execution, args['execution_id'],
                )._storage_id
            plugins_update.deployments_to_update = args.get(
                'affected_deployments', [])
            if args.get('temp_blueprint_id'):
                plugins_update.temp_blueprint = update_manager.sm.get(
                    models.Blueprint, args['temp_blueprint_id'])

            return update_manager.sm.put(plugins_update)

        if phase == PHASES.INITIAL:
            return update_manager.initiate_plugins_update(
                blueprint_id=id, filters=filters,
                auto_correct_types=auto_correct_types,
                reevaluate_active_statuses=reevaluate_active_statuses,
                all_tenants=args.get('all_tenants', False),
            )
        elif phase == PHASES.FINAL:
            return update_manager.finalize(plugins_update_id=id)


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

    @authorize('plugin_upload')
    def patch(self, plugin_id, **kwargs):
        """Update the plugin, specifically its owner.

        Only updating the ownership is supported right now.
        """
        request_dict = rest_utils.get_json_and_verify_params({
            'creator': {'type': text_type, 'optional': True},
            'blueprint_labels': {'type': dict, 'optional': True},
            'labels': {'type': dict, 'optional': True},
        })
        sm = get_storage_manager()
        plugin = sm.get(models.Plugin, plugin_id)
        if 'creator' in request_dict:
            check_user_action_allowed('set_owner', None, True)
            creator = rest_utils.valid_user(request_dict['creator'])
            plugin.creator = creator
        for key in ['blueprint_labels', 'labels', 'resource_tags']:
            if key not in request_dict:
                continue
            setattr(plugin, key, request_dict[key])
        sm.update(plugin)
        return plugin.to_response()


class PluginsYaml(SecuredResource):
    """
    GET = download previously uploaded plugin yaml.
    """
    @swagger.operation(
        responseClass='YAML file',
        nickname="downloadPluginYaml",
        notes="download a plugin YAML according to the plugin ID. "
    )
    @authorize('plugin_download')
    def get(self, plugin_id, **kwargs):
        """
        Download plugin yaml
        """
        plugin = get_storage_manager().get(models.Plugin, plugin_id)
        return rest_utils.make_streaming_response(
            plugin_id,
            plugin.file_server_path,
            'yaml'
        )

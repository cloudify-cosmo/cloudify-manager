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

import os
import uuid

from flask import current_app

from cloudify.models_states import ExecutionState, BlueprintUploadState

from dsl_parser.constants import (PLUGIN_NAME_KEY,
                                  WORKFLOW_PLUGINS_TO_INSTALL,
                                  DEPLOYMENT_PLUGINS_TO_INSTALL,
                                  HOST_AGENT_PLUGINS_TO_INSTALL,
                                  PLUGIN_PACKAGE_NAME,
                                  PLUGIN_PACKAGE_VERSION)

from manager_rest import config, utils
from manager_rest.storage import get_storage_manager, models
from manager_rest.resource_manager import get_resource_manager
from manager_rest.plugins_update.constants import (STATES,
                                                   ACTIVE_STATES,
                                                   PLUGIN_NAMES,
                                                   TO_LATEST,
                                                   ALL_TO_LATEST,
                                                   TO_MINOR,
                                                   ALL_TO_MINOR,
                                                   MAPPING,
                                                   UPDATES,
                                                   PLUGIN_NAME,
                                                   SUGGESTED_VERSION)
from manager_rest.manager_exceptions import (ConflictError,
                                             PluginsUpdateError,
                                             IllegalActionError)
from manager_rest.constants import FILE_SERVER_BLUEPRINTS_FOLDER


PLUGIN_VERSION_CONSTRAINTS = 'plugin_version_constraints'
PLUGIN_MAPPINGS = 'plugin_mappings'


class PluginsUpdateManager(object):
    def __init__(self, sm):
        self.sm = sm
        self.rm = get_resource_manager(self.sm)

    def validate_no_active_updates_per_blueprint(self, blueprint_id):
        active_updates = self.list_plugins_updates(
            filters={'blueprint_id': blueprint_id,
                     'state': ACTIVE_STATES}).items
        if not active_updates:
            return

        raise ConflictError(
            'There are plugins updates still active, update IDs: '
            '{0}'.format(', '.join(u.id for u in active_updates)))

    def _create_temp_blueprint_from(self, blueprint, temp_plan):
        temp_blueprint_id = str(uuid.uuid4())
        kwargs = {
            'application_file_name': blueprint.main_file_name,
            'blueprint_id': temp_blueprint_id,
            'plan': temp_plan
        }
        # Make sure not to pass both private resource and visibility
        visibility = blueprint.visibility
        if visibility:
            kwargs['visibility'] = visibility
            kwargs['private_resource'] = None
        else:
            kwargs['visibility'] = None
            kwargs['private_resource'] = blueprint.private_resource
        kwargs['state'] = BlueprintUploadState.UPLOADED
        temp_blueprint = self.rm.publish_blueprint_from_plan(**kwargs)
        temp_blueprint.is_hidden = True
        return self.sm.update(temp_blueprint)

    def _stage_plugin_update(self, blueprint, forced):
        update_id = str(uuid.uuid4())
        plugins_update = models.PluginsUpdate(
            id=update_id,
            created_at=utils.get_formatted_timestamp(),
            forced=forced)
        plugins_update.set_blueprint(blueprint)
        return self.sm.put(plugins_update)

    def initiate_plugins_update(self, blueprint_id, filters):
        """Creates a temporary blueprint and executes the plugins update
        workflow.
        """
        self.validate_no_active_updates_per_blueprint(blueprint_id)
        blueprint = self.sm.get(models.Blueprint, blueprint_id)
        temp_plan = self.get_reevaluated_plan(
            blueprint,
            {PLUGIN_VERSION_CONSTRAINTS:
             _plugin_version_constraints(blueprint, filters),
             PLUGIN_MAPPINGS:
             _plugin_mappings(blueprint, filters)}
        )

        changes_required = _did_plugins_to_install_change(temp_plan,
                                                          blueprint.plan)
        plugins_update = self._stage_plugin_update(blueprint,
                                                   filters.get('force', False))
        if changes_required:
            plugins_update.deployments_to_update = [
                dep.id for dep in self._get_deployments_to_update(blueprint_id)
            ]
            self.sm.update(plugins_update)

            temp_blueprint = self._create_temp_blueprint_from(blueprint,
                                                              temp_plan)
            plugins_update.temp_blueprint = temp_blueprint
            plugins_update.state = STATES.UPDATING
            self.sm.update(plugins_update)

        plugins_update.execution = get_resource_manager(
            self.sm).update_plugins(plugins_update, not changes_required)
        plugins_update.state = (STATES.EXECUTING_WORKFLOW if changes_required
                                else STATES.NO_CHANGES_REQUIRED)
        return self.sm.update(plugins_update)

    def finalize(self, plugins_update_id):
        """Executes the following procedure:
        * Updates the original blueprint plan
        * Changes all the deployments' blueprint back from the temp blueprint
           to the original one
        * Deletes the temporary blueprint
        * Updates the plugins update state
        """
        plugins_update = self.sm.get(models.PluginsUpdate, plugins_update_id)

        self._validate_plugins_update_state(plugins_update)
        self._validate_execution_status(plugins_update)

        plugins_update.state = STATES.FINALIZING
        self.sm.update(plugins_update)

        plugins_update.blueprint.plan = plugins_update.temp_blueprint.plan
        self.sm.update(plugins_update.blueprint)

        updated_deployments = self._get_deployments_to_update(
            plugins_update.temp_blueprint_id)

        for dep in updated_deployments:
            dep.blueprint = plugins_update.blueprint
            dep.updated_at = utils.get_formatted_timestamp()
            self.sm.update(dep)

        self.sm.delete(plugins_update.temp_blueprint)

        plugins_update.state = STATES.SUCCESSFUL
        return self.sm.update(plugins_update)

    @staticmethod
    def _validate_plugins_update_state(plugins_update):
        if plugins_update.state != STATES.EXECUTING_WORKFLOW:
            raise IllegalActionError(
                "Cannot finalize plugins update {0}, "
                "it's not in the {1} state.".format(plugins_update.id,
                                                    STATES.EXECUTING_WORKFLOW))

    def _validate_execution_status(self, plugins_update):
        execution = self.sm.get(models.Execution, plugins_update.execution_id)
        if (execution.status in ExecutionState.END_STATES
                and execution.status != ExecutionState.TERMINATED):
            plugins_update.state = STATES.FAILED
            self.sm.update(plugins_update)
            raise PluginsUpdateError(
                'The execution of plugins update {0} {1}.'.format(
                    plugins_update.id,
                    execution.status.lower()))

    def _get_deployments_to_update(self, blueprint_id):
        return self.sm.list(models.Deployment,
                            filters={'blueprint_id': blueprint_id},
                            sort={'id': 'asc'}).items

    def get_plugins_update(self, plugins_update_id):
        return self.sm.get(models.PluginsUpdate, plugins_update_id)

    def list_plugins_updates(self,
                             include=None,
                             filters=None,
                             pagination=None,
                             sort=None,
                             substr_filters=None):
        return self.sm.list(models.PluginsUpdate,
                            include=include,
                            filters=filters,
                            pagination=pagination,
                            substr_filters=substr_filters,
                            sort=sort)

    def get_reevaluated_plan(self, blueprint, resolver_parameters):
        blueprint_dir = os.path.join(
            config.instance.file_server_root,
            FILE_SERVER_BLUEPRINTS_FOLDER,
            blueprint.tenant.name,
            blueprint.id)
        temp_plan = self.rm.parse_plan(blueprint_dir,
                                       blueprint.main_file_name,
                                       config.instance.file_server_root,
                                       resolver_parameters=resolver_parameters)
        return temp_plan


def _plugins_in_a_plan(plan):
    for plugins_key in [DEPLOYMENT_PLUGINS_TO_INSTALL,
                        WORKFLOW_PLUGINS_TO_INSTALL,
                        HOST_AGENT_PLUGINS_TO_INSTALL]:
        if plugins_key not in plan:
            continue
        for a_plugin in plan[plugins_key]:
            if a_plugin[PLUGIN_PACKAGE_NAME] and \
                    a_plugin[PLUGIN_PACKAGE_VERSION]:
                yield a_plugin


def _exact_version_constraint(version):
    return '=={0}'.format(version)


def _minor_version_constraint(version):
    v = version.split('.')
    return '>={0}.{1},<{2}'.format(v[0], v[1], int(v[0]) + 1)


def _plugin_version_constraints(blueprint, filters):
    """Prepare a list of plugin version constraints for the resolver."""

    def prepare_constraint(plugin_name, plugin_version, filters):
        # If filtering by plugin names are `plugin_name` is not listed as one
        # of them, current version of the plugin is mandatory (no upgrade)
        if filters.get(PLUGIN_NAMES) and \
                plugin_name not in filters[PLUGIN_NAMES]:
            return _exact_version_constraint(plugin_version)
        # If all plugins should be upgraded to the latest version and this
        # particular plugin is listed in to_minor list, then return minor
        # version constraints
        if filters.get(ALL_TO_LATEST):
            if plugin_name in filters.get(TO_MINOR, []):
                return _minor_version_constraint(plugin_version)
            else:
                return None
        # If all plugins should be upgraded to the latest minor version and
        # this particular plugin is not listed in to_latest list, then return
        # minor version constraints
        if filters.get(ALL_TO_MINOR):
            if plugin_name in filters.get(TO_LATEST, []):
                return None
            else:
                return _minor_version_constraint(plugin_version)
        return None

    constraints = {}
    for plugin in _plugins_in_a_plan(blueprint.plan):
        if plugin[PLUGIN_PACKAGE_NAME] in constraints:
            continue
        constraint = prepare_constraint(plugin[PLUGIN_PACKAGE_NAME],
                                        plugin[PLUGIN_PACKAGE_VERSION],
                                        filters)
        if constraint:
            constraints[plugin[PLUGIN_PACKAGE_NAME]] = constraint

    return constraints


def _plugin_mappings(blueprint, filters):
    """Prepare a list of plugin version mappings for the resolver."""

    def prepare_mapping(plugin_name, mapping_updates):
        # If there is one and only one mapping for a specific plugin
        # name/version then use the suggested version from the mapping file
        for mapping_update in mapping_updates:
            for blueprint_line, mapping in mapping_update.items():
                if plugin_name == mapping.get(PLUGIN_NAME):
                    return {
                        'version': _exact_version_constraint(
                            mapping.get(SUGGESTED_VERSION)),
                        'import_url': blueprint_line,
                    }

    if not filters.get(MAPPING, {}).get(UPDATES):
        return {}
    mappings = {}
    for plugin in _plugins_in_a_plan(blueprint.plan):
        if plugin[PLUGIN_PACKAGE_NAME] in mappings:
            continue
        mapping = prepare_mapping(plugin[PLUGIN_PACKAGE_NAME],
                                  filters.get(MAPPING).get(UPDATES))
        if mapping:
            mappings[plugin[PLUGIN_PACKAGE_NAME]] = mapping

    return mappings


def _did_plugins_to_install_change(temp_plan, plan):
    # Maintaining backward comparability for older blueprints
    if not plan.get(HOST_AGENT_PLUGINS_TO_INSTALL):
        plan[HOST_AGENT_PLUGINS_TO_INSTALL] = \
            utils.extract_host_agent_plugins_from_plan(plan)

    return any(
        _did_executor_plugins_to_install_change(temp_plan, plan, executor)
        for executor in [DEPLOYMENT_PLUGINS_TO_INSTALL,
                         WORKFLOW_PLUGINS_TO_INSTALL,
                         HOST_AGENT_PLUGINS_TO_INSTALL])


def _did_executor_plugins_to_install_change(temp_plan, plan, plugins_executor):
    temp_plugins = temp_plan[plugins_executor]
    current_plugins = plan[plugins_executor]
    name_to_plugin = {p[PLUGIN_NAME_KEY]: p for p in current_plugins}
    return any(plugin for plugin in temp_plugins
               if plugin != name_to_plugin.get(plugin[PLUGIN_NAME_KEY], None))


def get_plugins_updates_manager():
    return current_app.config.setdefault(
        'plugins_updates_manager',
        PluginsUpdateManager(get_storage_manager())
    )

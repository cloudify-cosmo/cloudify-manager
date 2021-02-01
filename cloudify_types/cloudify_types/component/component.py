# Copyright (c) 2017-2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import time

from cloudify import manager, ctx
from cloudify._compat import urlparse
from cloudify.constants import COMPONENT
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify.deployment_dependencies import (dependency_creator_generator,
                                              create_deployment_dependency)

from .constants import (
    EXECUTIONS_TIMEOUT,
    POLLING_INTERVAL,
    EXTERNAL_RESOURCE)
from .polling import (
    poll_with_timeout,
    is_all_executions_finished,
    verify_execution_state,
    wait_for_blueprint_to_upload
)
from .utils import (
    blueprint_id_exists,
    deployment_id_exists,
    update_runtime_properties,
    get_local_path,
    zip_files,
    should_upload_plugin,
    populate_runtime_with_wf_results
)


class Component(object):

    @staticmethod
    def _get_desired_operation_input(key,
                                     args):
        """ Resolving a key's value from kwargs or
        runtime properties, node properties in the order of priority.
        """
        return (args.get(key) or
                ctx.instance.runtime_properties.get(key) or
                ctx.node.properties.get(key))

    def __init__(self, operation_inputs):
        """
        Sets the properties that all operations need.
        :param operation_inputs: The inputs from the operation.
        """

        full_operation_name = ctx.operation.name
        self.operation_name = full_operation_name.split('.').pop()

        # Cloudify client setup
        self.client_config = self._get_desired_operation_input(
            'client', operation_inputs)

        if self.client_config:
            self.client = CloudifyClient(**self.client_config)
        else:
            self.client = manager.get_rest_client()

        self.plugins = self._get_desired_operation_input(
            'plugins', operation_inputs)
        self.secrets = self._get_desired_operation_input(
            'secrets', operation_inputs)
        self.config = self._get_desired_operation_input(
            'resource_config', operation_inputs)

        # Blueprint-related properties
        self.blueprint = self.config.get('blueprint', {})
        self.blueprint_id = self.blueprint.get('id') or ctx.instance.id
        self.blueprint_file_name = self.blueprint.get('main_file_name')
        self.blueprint_archive = self.blueprint.get('blueprint_archive')

        # Deployment-related properties
        runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
        runtime_deployment_id = runtime_deployment_prop.get('id')

        self.deployment = self.config.get('deployment', {})
        self.deployment_id = (runtime_deployment_id or
                              self.deployment.get('id') or
                              ctx.instance.id)
        self.deployment_inputs = self.deployment.get('inputs', {})
        self.deployment_capabilities = self.deployment.get('capabilities')
        self.deployment_log_redirect = self.deployment.get('logs', True)
        self.deployment_auto_suffix = self.deployment.get('auto_inc_suffix',
                                                          False)

        # Execution-related properties
        self.workflow_id = operation_inputs.get(
            'workflow_id',
            'create_deployment_environment')
        self.workflow_state = operation_inputs.get('workflow_state',
                                                   'terminated')

        # Polling-related properties
        self.interval = operation_inputs.get('interval', POLLING_INTERVAL)
        self.state = operation_inputs.get('state', 'terminated')
        self.timeout = operation_inputs.get('timeout', EXECUTIONS_TIMEOUT)

        # Inter-Deployment Dependency identifier
        self._inter_deployment_dependency = create_deployment_dependency(
            dependency_creator_generator(COMPONENT,
                                         ctx.instance.id),
            ctx.deployment.id)

    def _http_client_wrapper(self,
                             option,
                             request_action,
                             request_args=None):
        """
        wrapper for http client requests with CloudifyClientError custom
        handling.
        :param option: can be blueprints, executions and etc.
        :param request_action: action to be done, like list, get and etc.
        :param request_args: args for the actual call.
        :return: The http response.
        """
        request_args = request_args or dict()
        generic_client = getattr(self.client, option)
        option_client = getattr(generic_client, request_action)

        try:
            return option_client(**request_args)
        except CloudifyClientError as ex:
            raise NonRecoverableError(
                'Client action "{0}" failed: {1}.'.format(request_action,
                                                          ex))

    @staticmethod
    def _is_valid_url(candidate):
        parse_url = urlparse(candidate)
        return not (parse_url.netloc and parse_url.scheme)

    def _upload_if_not_existing(self):
        try:
            self.client.blueprints._upload(
                blueprint_id=self.blueprint_id,
                archive_location=self.blueprint_archive,
                application_file_name=self.blueprint_file_name)
            wait_for_blueprint_to_upload(self.blueprint_id, self.client)
        except CloudifyClientError as ex:
            if 'already exists' not in str(ex):
                raise NonRecoverableError(
                    'Client action "_upload" failed: {0}.'.format(ex))
        return True

    def upload_blueprint(self):
        if 'blueprint' not in ctx.instance.runtime_properties:
            ctx.instance.runtime_properties['blueprint'] = dict()

        update_runtime_properties('blueprint', 'id', self.blueprint_id)
        update_runtime_properties(
            'blueprint', 'blueprint_archive', self.blueprint_archive)
        update_runtime_properties(
            'blueprint', 'application_file_name', self.blueprint_file_name)

        blueprint_exists = blueprint_id_exists(self.client, self.blueprint_id)

        if self.blueprint.get(EXTERNAL_RESOURCE) and not blueprint_exists:
            raise NonRecoverableError(
                'Blueprint ID \"{0}\" does not exist, '
                'but {1} is {2}.'.format(
                    self.blueprint_id,
                    EXTERNAL_RESOURCE,
                    self.blueprint.get(EXTERNAL_RESOURCE)))
        elif self.blueprint.get(EXTERNAL_RESOURCE) and blueprint_exists:
            ctx.logger.info("Using external blueprint.")
            return True
        elif blueprint_exists:
            ctx.logger.info(
                'Blueprint ID "{0}" exists, '
                'but {1} is {2}, will use the existing one.'.format(
                    self.blueprint_id,
                    EXTERNAL_RESOURCE,
                    self.blueprint.get(EXTERNAL_RESOURCE)))
            return True
        if not self.blueprint_archive:
            raise NonRecoverableError(
                'No blueprint_archive supplied, '
                'but {0} is False'.format(EXTERNAL_RESOURCE))

        # Check if the ``blueprint_archive`` is not a URL then we need to
        # download it and pass the binaries to the client_args
        if self._is_valid_url(self.blueprint_archive):
            self.blueprint_archive = ctx.download_resource(
                self.blueprint_archive)

        return self._upload_if_not_existing()

    def _upload_plugins(self):
        if (not self.plugins or
                'plugins' in ctx.instance.runtime_properties):
            # No plugins to install or already uploaded them.
            return

        ctx.instance.runtime_properties['plugins'] = []
        existing_plugins = self._http_client_wrapper(
                    'plugins', 'list')

        for plugin_name, plugin in self.plugins.items():
            zip_list = []
            zip_path = None
            try:
                if (not plugin.get('wagon_path') or
                        not plugin.get('plugin_yaml_path')):
                    raise NonRecoverableError(
                        'You should provide both values wagon_path: {}'
                        ' and plugin_yaml_path: {}'
                        .format(repr(plugin.get('wagon_path')),
                                repr(plugin.get('plugin_yaml_path'))))
                wagon_path = get_local_path(plugin['wagon_path'],
                                            create_temp=True)
                yaml_path = get_local_path(plugin['plugin_yaml_path'],
                                           create_temp=True)
                zip_list = [wagon_path, yaml_path]
                if 'icon_png_path' in plugin:
                    icon_path = get_local_path(plugin['icon_png_path'],
                                               create_temp=True)
                    zip_list.append(icon_path)
                if not should_upload_plugin(yaml_path, existing_plugins):
                    ctx.logger.warn('Plugin "{0}" was already '
                                    'uploaded...'.format(plugin_name))
                    continue

                ctx.logger.info('Creating plugin "{0}" zip '
                                'archive...'.format(plugin_name))
                zip_path = zip_files(zip_list)

                # upload plugin
                plugin = self._http_client_wrapper(
                    'plugins', 'upload', {'plugin_path': zip_path})
                ctx.instance.runtime_properties['plugins'].append(
                    plugin.id)
                ctx.logger.info('Uploaded {}'.format(repr(plugin.id)))
            finally:
                for f in zip_list:
                    os.remove(f)
                if zip_path:
                    os.remove(zip_path)

    def _verify_secrets_clash(self):
        existing_secrets = {secret.key: secret.value
                            for secret in
                            self._http_client_wrapper('secrets', 'list')}

        duplicate_secrets = set(self.secrets).intersection(existing_secrets)

        if duplicate_secrets:
            raise NonRecoverableError('The secrets: {0} already exist, '
                                      'not updating...'.format(
                                        '"' + '", "'.join(duplicate_secrets)
                                        + '"'))

    def _set_secrets(self):
        if not self.secrets:
            return

        self._verify_secrets_clash()

        for secret_name in self.secrets:
            self._http_client_wrapper('secrets', 'create', {
                'key': secret_name,
                'value': u'{0}'.format(self.secrets[secret_name]),
            })
            ctx.logger.info('Created secret {}'.format(repr(secret_name)))

    @staticmethod
    def _generate_suffix_deployment_id(client, deployment_id):
        dep_exists = True
        suffix_index = ctx.instance.runtime_properties['deployment'].get(
            'current_suffix_index', 0)

        while dep_exists:
            suffix_index += 1
            inc_deployment_id = '{0}-{1}'.format(deployment_id, suffix_index)
            dep_exists = deployment_id_exists(client, inc_deployment_id)

        update_runtime_properties('deployment',
                                  'current_suffix_index',
                                  suffix_index)
        return inc_deployment_id

    def create_deployment(self):
        self._set_secrets()
        self._upload_plugins()

        if 'deployment' not in ctx.instance.runtime_properties:
            ctx.instance.runtime_properties['deployment'] = dict()

        if self.deployment_auto_suffix:
            self.deployment_id = self._generate_suffix_deployment_id(
                self.client, self.deployment_id)
        elif deployment_id_exists(self.client, self.deployment_id):
            raise NonRecoverableError(
                'Component\'s deployment ID "{0}" already exists, '
                'please verify the chosen name.'.format(
                    self.deployment_id))
        self._inter_deployment_dependency['target_deployment'] = \
            self.deployment_id

        update_runtime_properties('deployment', 'id', self.deployment_id)
        ctx.logger.info('Creating "{0}" component deployment.'
                        .format(self.deployment_id))

        self._http_client_wrapper('deployments', 'create', {
            'blueprint_id': self.blueprint_id,
            'deployment_id': self.deployment_id,
            'inputs': self.deployment_inputs
        })

        self._http_client_wrapper('inter_deployment_dependencies',
                                  'create',
                                  self._inter_deployment_dependency)

        # Prepare executions list fields
        execution_list_fields = ['workflow_id', 'id']

        # Call list executions for the current deployment
        executions = self._http_client_wrapper('executions', 'list', {
            'deployment_id': self.deployment_id,
            '_include': execution_list_fields
        })

        # Retrieve the ``execution_id`` associated with the current deployment
        execution_id = [execution.get('id') for execution in executions
                        if (execution.get('workflow_id') ==
                            'create_deployment_environment')]

        # If the ``execution_id`` cannot be found raise error
        if not execution_id:
            raise NonRecoverableError(
                'No execution Found for component "{}"'
                ' deployment'.format(self.deployment_id)
            )

        # If a match was found there can only be one, so we will extract it.
        execution_id = execution_id[0]
        ctx.logger.info('Found execution id "{0}" for deployment id "{1}"'
                        .format(execution_id,
                                self.deployment_id))
        return self.verify_execution_successful(execution_id)

    def _try_to_remove_plugin(self, plugin_id):
        try:
            self.client.plugins.delete(plugin_id=plugin_id)
        except CloudifyClientError as ex:
            if 'currently in use in blueprints' in str(ex):
                ctx.logger.warn('Could not remove plugin "{0}", it '
                                'is currently in use...'.format(plugin_id))
            else:
                raise NonRecoverableError('Failed to remove plugin '
                                          '"{0}"....'.format(plugin_id))

    def _delete_plugins(self):
        plugins = ctx.instance.runtime_properties.get('plugins', [])

        for plugin_id in plugins:
            self._try_to_remove_plugin(plugin_id)
            ctx.logger.info('Removed plugin "{0}".'.format(plugin_id))

    def _delete_secrets(self):
        if not self.secrets:
            return

        for secret_name in self.secrets:
            self._http_client_wrapper('secrets', 'delete', {
                'key': secret_name,
            })
            ctx.logger.info('Removed secret "{}"'.format(repr(secret_name)))

    @staticmethod
    def _delete_runtime_properties():
        for property_name in ['deployment', 'blueprint', 'plugins']:
            if property_name in ctx.instance.runtime_properties:
                del ctx.instance.runtime_properties[property_name]

    def delete_deployment(self):
        ctx.logger.info("Wait for component's stop deployment operation "
                        "related executions.")
        poll_with_timeout(
            lambda:
            is_all_executions_finished(self.client,
                                       self.deployment_id),
            timeout=self.timeout,
            expected_result=True)

        ctx.logger.info('Delete component\'s "{0}" deployment'
                        .format(self.deployment_id))

        poll_result = True
        if not deployment_id_exists(self.client, self.deployment_id):
            # Could happen in case that deployment failed to install
            ctx.logger.warn('Didn\'t find component\'s "{0}" deployment,'
                            'so nothing to do and moving on.'
                            .format(self.deployment_id))
        else:
            self._http_client_wrapper('deployments',
                                      'delete',
                                      dict(deployment_id=self.deployment_id))

            ctx.logger.info("Waiting for component's deployment delete.")
            poll_result = poll_with_timeout(
                lambda: deployment_id_exists(self.client, self.deployment_id),
                timeout=self.timeout,
                expected_result=False)

        ctx.logger.debug("Internal services cleanup.")
        time.sleep(POLLING_INTERVAL)

        ctx.logger.debug("Waiting for all system workflows to stop/finish.")
        poll_with_timeout(
            lambda: is_all_executions_finished(self.client),
            timeout=self.timeout,
            expected_result=True)

        if not self.blueprint.get(EXTERNAL_RESOURCE):
            ctx.logger.info('Delete component\'s blueprint "{0}".'
                            .format(self.blueprint_id))
            self._http_client_wrapper('blueprints',
                                      'delete',
                                      dict(blueprint_id=self.blueprint_id))

        ctx.logger.info('Removing inter-deployment dependency between this '
                        'deployment ("{0}") and "{1}" the Component\'s '
                        'creator deployment...'.format(self.deployment_id,
                                                       ctx.deployment.id))
        self._inter_deployment_dependency['target_deployment'] = \
            self.deployment_id
        self._inter_deployment_dependency['is_component_deletion'] = True
        self.client.inter_deployment_dependencies.delete(
            **self._inter_deployment_dependency)

        self._delete_plugins()
        self._delete_secrets()
        self._delete_runtime_properties()

        return poll_result

    def execute_workflow(self):
        # Wait for the deployment to finish any executions
        if not poll_with_timeout(lambda:
                                 is_all_executions_finished(
                                     self.client, self.deployment_id),
                                 timeout=self.timeout,
                                 expected_result=True):
            return ctx.operation.retry(
                'The "{0}" deployment is not ready for execution.'.format(
                    self.deployment_id))

        execution_args = self.config.get('executions_start_args', {})

        request_args = dict(
            deployment_id=self.deployment_id,
            workflow_id=self.workflow_id,
            **execution_args
        )
        if self.workflow_id == ctx.workflow_id:
            request_args.update(dict(parameters=ctx.workflow_parameters))

        ctx.logger.info('Starting execution for "{0}" deployment'.format(
            self.deployment_id))
        execution = self._http_client_wrapper(
            'executions', 'start', request_args)

        ctx.logger.debug('Execution start response: "{0}".'.format(execution))

        execution_id = execution['id']
        if not self.verify_execution_successful(execution_id):
            ctx.logger.error('Execution {0} failed for "{1}" '
                             'deployment'.format(execution_id,
                                                 self.deployment_id))

        ctx.logger.info('Execution succeeded for "{0}" deployment'.format(
            self.deployment_id))
        populate_runtime_with_wf_results(self.client, self.deployment_id)
        return True

    def verify_execution_successful(self, execution_id):
        return verify_execution_state(self.client,
                                      execution_id,
                                      self.deployment_id,
                                      self.deployment_log_redirect,
                                      self.workflow_state,
                                      self.timeout,
                                      self.interval)

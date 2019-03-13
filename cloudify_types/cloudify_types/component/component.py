# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import sys
import time
import os
from urlparse import urlparse

from cloudify import manager, ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.utils import exception_to_error_cause
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from .constants import (
    EXECUTIONS_TIMEOUT,
    POLLING_INTERVAL,
    EXTERNAL_RESOURCE)
from .polling import (
    blueprint_id_exists,
    deployment_id_exists,
    poll_with_timeout,
    poll_workflow_after_execute,
    is_all_executions_finished
)
from cloudify_types.component.utils import (
    update_runtime_properties,
    get_local_path,
    zip_files
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
        runtime_deployment_id = ctx.instance.runtime_properties.get('deployment', {}).get('id')

        self.deployment = self.config.get('deployment', {})
        self.deployment_id = runtime_deployment_id or self.deployment.get('id') or ctx.instance.id
        self.deployment_inputs = self.deployment.get('inputs', {})
        self.deployment_outputs = self.deployment.get('outputs', {})
        self.deployment_logs = self.deployment.get('logs', {})
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

        # This ``execution_id`` will be set once execute workflow done
        # successfully
        self.execution_id = None

    def _http_client_wrapper(self,
                             option,
                             request_action,
                             request_args):
        """
        wrapper for http client requests with CloudifyClientError custom
        handling.
        :param option: can be blueprints, executions and etc.
        :param request_action: action to be done, like list, get and etc.
        :param request_args: args for the actual call.
        :return: The http response.
        """
        generic_client = getattr(self.client, option)
        option_client = getattr(generic_client, request_action)

        try:
            return option_client(**request_args)
        except CloudifyClientError as ex:
            raise NonRecoverableError(
                'Client action \"{0}\" failed: {1}.'.format(request_action,
                                                            ex))

    @staticmethod
    def _is_valid_url(candidate):
        parse_url = urlparse(candidate)
        return not (parse_url.netloc and parse_url.scheme)

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
                'Blueprint ID {0} does not exist, '
                'but {1} is {2}.'.format(
                    self.blueprint_id,
                    EXTERNAL_RESOURCE,
                    self.blueprint.get(EXTERNAL_RESOURCE)))
        elif self.blueprint.get(EXTERNAL_RESOURCE) and blueprint_exists:
            ctx.logger.info("Used external blueprint.")
            return False
        elif blueprint_exists:
            ctx.logger.warn(
                'Blueprint ID {0} exists, '
                'but {1} is {2}. Will use.'.format(
                    self.blueprint_id,
                    EXTERNAL_RESOURCE,
                    self.blueprint.get(EXTERNAL_RESOURCE)))
            return False
        if not self.blueprint_archive:
            raise NonRecoverableError(
                'No blueprint_archive supplied, '
                'but {0} is False'.format(EXTERNAL_RESOURCE))

        # Check if the ``blueprint_archive`` is not a URL then we need to
        # download it and pass the binaries to the client_args
        if self._is_valid_url(self.blueprint_archive):
            self.blueprint_archive = ctx.download_resource(
                self.blueprint_archive)

        client_args = dict(blueprint_id=self.blueprint_id,
                           archive_location=self.blueprint_archive,
                           application_file_name=self.blueprint_file_name)

        return self._http_client_wrapper('blueprints',
                                         '_upload',
                                         client_args)

    def _upload_plugins(self):
        if not self.plugins:
            return

        if 'plugins' not in ctx.instance.runtime_properties:
            ctx.instance.runtime_properties['plugins'] = []

        if isinstance(self.plugins, dict):
            plugins_list = self.plugins.values()
        else:
            raise NonRecoverableError(
                'Wrong type in plugins: {}'.format(repr(self.plugins)))

        for plugin in plugins_list:
            ctx.logger.info('Creating plugin zip archive..')
            wagon_path = None
            yaml_path = None
            zip_path = None
            try:
                if (
                    not plugin.get('wagon_path') or
                    not plugin.get('plugin_yaml_path')
                ):
                    raise NonRecoverableError(
                        'You should provide both values wagon_path: {}'
                        ' and plugin_yaml_path: {}'
                        .format(repr(plugin.get('wagon_path')),
                                repr(plugin.get('plugin_yaml_path'))))
                wagon_path = get_local_path(plugin['wagon_path'],
                                            create_temp=True)
                yaml_path = get_local_path(plugin['plugin_yaml_path'],
                                           create_temp=True)
                zip_path = zip_files([wagon_path, yaml_path])

                # upload plugin
                plugin = self._http_client_wrapper(
                    'plugins', 'upload', {'plugin_path': zip_path})
                ctx.instance.runtime_properties['plugins'].append(
                    plugin.id)
                ctx.logger.info('Uploaded {}'.format(repr(plugin.id)))
            finally:
                if wagon_path:
                    os.remove(wagon_path)
                if yaml_path:
                    os.remove(yaml_path)
                if zip_path:
                    os.remove(zip_path)

    def _set_secrets(self):
        if not self.secrets:
            return

        for secret_name in self.secrets:
            self._http_client_wrapper('secrets', 'create', {
                'key': secret_name,
                'value': self.secrets[secret_name],
            })
            ctx.logger.info('Created secret {}'.format(repr(secret_name)))

    @staticmethod
    def _generate_suffix_deployment_id(client, deployment_id):
        dep_exists = True
        while dep_exists:
            suffix_index = ctx.instance.runtime_properties['deployment'].get(
                'current_suffix_index', 1)
            inc_id = '{}-{}'.format(deployment_id, suffix_index)
            update_runtime_properties('deployment',
                                      'current_suffix_index',
                                      suffix_index + 1)
            dep_exists = deployment_id_exists(client, inc_id)
        return inc_id

    def create_deployment(self):
        self._set_secrets()
        self._upload_plugins()

        if 'deployment' not in ctx.instance.runtime_properties:
            ctx.instance.runtime_properties['deployment'] = dict()

        if self.deployment_auto_suffix:
            self.deployment_id = self._generate_suffix_deployment_id(
                self.client, self.deployment_id)
        elif deployment_id_exists(self.client, self.deployment_id):
            ctx.logger.error(
                'Component\'s deployment ID {} already exists, '
                'please verify the chosen name.'.format(
                    self.blueprint_id))
            return False

        update_runtime_properties('deployment', 'id', self.deployment_id)
        ctx.logger.info("Create \"{0}\" component deployment."
                        .format(self.deployment_id))

        self._http_client_wrapper('deployments',
                                  'create',
                                  {
                                      'blueprint_id': self.blueprint_id,
                                      'deployment_id': self.deployment_id,
                                      'inputs': self.deployment_inputs
                                  }
                                  )

        # In order to set the ``self.execution_id`` need to get the
        # ``execution_id`` of current deployment ``self.deployment_id``

        # Prepare executions list fields
        execution_list_fields = ['workflow_id', 'id']

        # Call list executions for the current deployment
        executions = self._http_client_wrapper(
            'executions', 'list',
            {
                'deployment_id': self.deployment_id,
                '_include': execution_list_fields
            }
        )

        # Retrieve the ``execution_id`` associated with the current deployment
        self.execution_id = [execution.get('id') for execution in executions
                             if (execution.get('workflow_id') ==
                                 'create_deployment_environment')]

        # If the ``execution_id`` cannot be found raise error
        if not self.execution_id:
            raise NonRecoverableError(
                'No execution id Found for deployment'
                ' {0}'.format(self.deployment_id)
            )

        # If a match was found there can only be one, so we will extract it.
        self.execution_id = self.execution_id[0]
        ctx.logger.info("Found execution_id {0} for deployment_id {1}"
                        .format(self.execution_id,
                                self.deployment_id))
        return self.verify_execution_successful()

    def _delete_plugins(self):
        plugins = ctx.instance.runtime_properties.get('plugins', [])

        for plugin_id in plugins:
            self._http_client_wrapper('plugins', 'delete', {
                'plugin_id': plugin_id
            })
            ctx.logger.info('Removed plugin {}'.format(repr(plugin_id)))

    def _delete_secrets(self):
        if not self.secrets:
            return

        for secret_name in self.secrets:
            self._http_client_wrapper('secrets', 'delete', {
                'key': secret_name,
            })
            ctx.logger.info('Removed secret {}'.format(repr(secret_name)))

    @staticmethod
    def _delete_properties():
        for property_name in ['deployment', 'executions', 'blueprint',
                              'plugins']:
            if property_name in ctx.instance.runtime_properties:
                del ctx.instance.runtime_properties[property_name]

    def delete_deployment(self):
        delete_component_args = dict(deployment_id=self.deployment_id)

        ctx.logger.info("Wait for component's stop deployment operation "
                        "related executions.")
        poll_with_timeout(
            lambda:
            is_all_executions_finished(self.client,
                                       self.deployment_id),
            timeout=self.timeout,
            expected_result=True)

        ctx.logger.info("Delete component's \"{}\" deployment"
                        .format(self.deployment_id))
        self._http_client_wrapper('deployments',
                                  'delete',
                                  delete_component_args)

        ctx.logger.info("Wait for component's deployment delete.")
        poll_result = poll_with_timeout(
            lambda: deployment_id_exists(self.client, self.deployment_id),
            timeout=self.timeout,
            expected_result=False)

        ctx.logger.info("Little wait internal cleanup services.")
        time.sleep(POLLING_INTERVAL)
        ctx.logger.info("Wait for stop all system workflows.")

        poll_with_timeout(
            lambda: is_all_executions_finished(self.client),
            timeout=self.timeout,
            expected_result=True)

        if not self.blueprint.get(EXTERNAL_RESOURCE):
            ctx.logger.info("Delete component's blueprint {0}."
                            .format(self.blueprint_id))
            delete_component_args = dict(blueprint_id=self.blueprint_id)
            self._http_client_wrapper('blueprints',
                                      'delete',
                                      delete_component_args)

        self._delete_plugins()
        self._delete_secrets()
        self._delete_properties()

        return poll_result

    def execute_workflow(self):
        if 'executions' not in ctx.instance.runtime_properties:
            ctx.instance.runtime_properties['executions'] = dict()

        # Updating runtime properties with where we are in the deployment flow
        update_runtime_properties(
            'executions', 'workflow_id', self.workflow_id)

        # Wait for the deployment to finish any executions
        if not poll_with_timeout(lambda:
                                 is_all_executions_finished(
                                     self.client, self.deployment_id),
                                 timeout=self.timeout,
                                 expected_result=True):
            return ctx.operation.retry(
                'The \"{}\" deployment is not ready for execution.'.format(
                    self.deployment_id))

        execution_args = self.config.get('executions_start_args', {})

        ctx.logger.info('Starting execution for \"{0}\" deployment'.format(self.deployment_id))
        response = self._http_client_wrapper('executions',
                                             'start',
                                             dict(
                                                 deployment_id=
                                                 self.deployment_id,
                                                 workflow_id=self.workflow_id,
                                                 **execution_args
                                             ))

        # Set the execution_id for the last execution process created
        self.execution_id = response['id']
        ctx.logger.debug('Executions start response: {0}'.format(response))

        # Poll for execution success.
        if not self.verify_execution_successful():
            ctx.logger.error('Deployment error.')

        ctx.logger.debug('Polling execution succeeded')

        ctx.logger.info('Start post execute component')
        self.post_execute_component()
        ctx.logger.info('End post execute component')

        return True

    def post_execute_component(self):
        runtime_prop = ctx.instance.runtime_properties['deployment']
        ctx.logger.debug(
            'Runtime deployment properties {0}'.format(runtime_prop))

        if 'outputs' \
                not in ctx.instance.runtime_properties['deployment']:
            update_runtime_properties('deployment', 'outputs', dict())
            ctx.logger.debug('No component outputs exist.')

        try:
            ctx.logger.debug('Deployment Id is {0}'.format(self.deployment_id))
            response = self.client.deployments.outputs.get(self.deployment_id)
            ctx.logger.debug(
                'Deployment outputs response {0}'.format(response))

        except CloudifyClientError as ex:
            _, _, tb = sys.exc_info()
            raise NonRecoverableError(
                'Failed to query deployment outputs: {0}'
                ''.format(self.deployment_id),
                causes=[exception_to_error_cause(ex, tb)])
        else:
            dep_outputs = response.get('outputs')
            ctx.logger.debug('Deployment outputs: {0}'.format(dep_outputs))
            for key, val in self.deployment_outputs.items():
                ctx.instance.runtime_properties[
                    'deployment']['outputs'][val] = dep_outputs.get(key, '')

    def verify_execution_successful(self):
        return poll_workflow_after_execute(
            self.timeout,
            self.interval,
            self.client,
            self.deployment_id,
            self.workflow_state,
            self.execution_id,
            log_redirect=self.deployment_logs.get('redirect', True))

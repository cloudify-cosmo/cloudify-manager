# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

from cloudify import manager, ctx
from cloudify.constants import SHARED_RESOURCE
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.client import CloudifyClient
from cloudify.deployment_dependencies import (dependency_creator_generator,
                                              create_deployment_dependency)

from cloudify_types.utils import get_deployment_by_id
from cloudify_types.component.utils import (
    populate_runtime_with_wf_results)


class SharedResource(object):
    @staticmethod
    def _get_desired_operation_input(key,
                                     args):
        """ Resolving a key's value from kwargs or
        node properties in the order of priority.
        """
        return (args.get(key) or
                ctx.node.properties.get(key))

    def __init__(self, operation_inputs):
        full_operation_name = ctx.operation.name
        self.operation_name = full_operation_name.split('.').pop()

        # Cloudify client setup
        self.client_config = self._get_desired_operation_input(
            'client', operation_inputs)

        if self.client_config:
            self.client = CloudifyClient(**self.client_config)

            # for determining an external client:
            manager_ips = [mgr.private_ip for mgr in
                           manager.get_rest_client().manager.get_managers()]
            internal_hosts = ({'127.0.0.1', 'localhost'} | set(manager_ips))
            host = {self.client.host} if type(self.client.host) == str \
                else set(self.client.host)
            self.is_external_host = not (host & internal_hosts)
        else:
            self.client = manager.get_rest_client()
            self.is_external_host = False

        self.config = self._get_desired_operation_input(
            'resource_config', operation_inputs)

        self.deployment = self.config.get('deployment', '')
        self.deployment_id = self.deployment.get('id', '')
        self._inter_deployment_dependency = create_deployment_dependency(
            dependency_creator_generator(SHARED_RESOURCE,
                                         ctx.instance.id),
            ctx.deployment.id,
            self.deployment_id
        )
        if self.is_external_host:
            self._local_dependency_params = \
                self._inter_deployment_dependency.copy()
            self._local_dependency_params['target_deployment'] = ' '
            self._local_dependency_params['external_target'] = {
                'deployment': self.deployment_id,
                'client_config': self.client_config
            }
            self._inter_deployment_dependency['external_source'] = {
                'deployment': ctx.deployment.id,
                'tenant': ctx.tenant_name,
                'host': manager_ips
            }

    def _mark_verified_shared_resource_node(self):
        """
        Used to mark SharedResource node that is valid after verification
        that the deployment exists, which will be used be users like
        the UI.
        """
        ctx.instance.runtime_properties['deployment'] = {
            'id': self.deployment_id}

    def validate_deployment(self):
        ctx.logger.info('Validating that "{0}" SharedResource\'s deployment '
                        'exists...'.format(self.deployment_id))

        if self.is_external_host:
            manager.get_rest_client().inter_deployment_dependencies.create(
                **self._local_dependency_params)

        deployment = get_deployment_by_id(self.client, self.deployment_id)
        if not deployment:
            raise NonRecoverableError(
                'SharedResource\'s deployment ID "{0}" does not exist, '
                'please verify the given ID.'.format(
                    self.deployment_id))
        self._mark_verified_shared_resource_node()
        populate_runtime_with_wf_results(self.client, self.deployment_id)

        self.client.inter_deployment_dependencies.create(
            **self._inter_deployment_dependency)
        return True

    def remove_inter_deployment_dependency(self):
        runtime_deployment_prop = ctx.instance.runtime_properties.get(
            'deployment', {})
        runtime_deployment_id = runtime_deployment_prop.get('id')
        target_deployment = runtime_deployment_id or self.deployment_id
        ctx.logger.info('Removing inter-deployment dependency between this '
                        'deployment ("{0}") and "{1}" SharedResource\'s '
                        'deployment...'
                        ''.format(ctx.deployment.id,
                                  target_deployment))
        self._inter_deployment_dependency['target_deployment'] = \
            target_deployment

        if self.is_external_host:
            self._local_dependency_params['target_deployment'] = ' '
            manager.get_rest_client().inter_deployment_dependencies.delete(
                **self._local_dependency_params)

        self.client.inter_deployment_dependencies.delete(
            **self._inter_deployment_dependency)
        return True

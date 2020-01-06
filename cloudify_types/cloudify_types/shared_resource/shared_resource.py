# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.client import CloudifyClient

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
        else:
            self.client = manager.get_rest_client()

        self.config = self._get_desired_operation_input(
            'resource_config', operation_inputs)

        self.deployment = self.config.get('deployment', '')
        self.deployment_id = self.deployment.get('id', '')

    def _mark_verified_shared_resource_node(self):
        """
        Used to mark SharedResource node that is valid after verification
        that the deployment exists, which will be used be users like
        the UI.
        """
        ctx.instance.runtime_properties['deployment'] = {
            'id': self.deployment_id}

    def validate_deployment(self):
        ctx.logger.info('Validating "{0}" SharedResource\'s deployment '
                        'existing.'.format(self.deployment_id))
        deployment = get_deployment_by_id(self.client, self.deployment_id)
        if not deployment:
            raise NonRecoverableError(
                'SharedResource\'s deployment ID "{0}" does not exists, '
                'please verify the given ID.'.format(
                    self.deployment_id))
        self._mark_verified_shared_resource_node()
        populate_runtime_with_wf_results(self.client, self.deployment_id)
        return True

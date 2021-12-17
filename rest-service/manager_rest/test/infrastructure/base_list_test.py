#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
from datetime import datetime
from cloudify.models_states import DeploymentModificationState, ExecutionState
from manager_rest.storage import models
from manager_rest.test.base_test import BaseServerTestCase


class BaseListTest(BaseServerTestCase):

    def _node(self, node_id, **kwargs):
        node_params = {
            'id': node_id,
            'type': 'type1',
            'number_of_instances': 1,
            'deploy_number_of_instances': 1,
            'max_number_of_instances': 1,
            'min_number_of_instances': 1,
            'planned_number_of_instances': 1,
            'creator': self.user,
            'tenant': self.tenant,
        }
        node_params.update(kwargs)
        return models.Node(**node_params)

    def _instance(self, instance_id, **kwargs):
        instance_params = {
            'id': instance_id,
            'state': 'uninitialized',
            'index': 1,
            'creator': self.user,
            'tenant': self.tenant,
        }
        instance_params.update(kwargs)
        return models.NodeInstance(**instance_params)

    def _put_deployment_modification(self, deployment,
                                     modified_nodes=None,
                                     node_instances=None,
                                     nodes=None):
        models.DeploymentModification(
            modified_nodes=modified_nodes or {},
            node_instances=node_instances or {},
            status=DeploymentModificationState.FINISHED,
            deployment=deployment,
            creator=self.user,
            tenant=self.tenant,
        )

    def _put_n_plugins(self, number_of_plugins):
        for i in range(number_of_plugins):
            models.Plugin(
                id=f'plugin{i}',
                archive_name='',
                package_name='cloudify-script-plugin',
                wheels=[],
                uploaded_at=datetime.now(),
                creator=self.user,
                tenant=self.tenant,
            )

    def _put_n_deployments(self, id_prefix, number_of_deployments):
        deployments = []
        for i in range(number_of_deployments):
            blueprint_id = f"{id_prefix}{i}_blueprint"
            bp = models.Blueprint(
                id=blueprint_id,
                creator=self.user,
                tenant=self.tenant,
            )
            bp.upload_execution = models.Execution(
                workflow_id='upload_blueprint',
                status=ExecutionState.TERMINATED,
                creator=self.user,
                tenant=self.tenant,
            )
            deployment_id = f"{id_prefix}{i}_deployment"

            deployment = models.Deployment(
                id=deployment_id,
                blueprint=bp,
                scaling_groups={},
                creator=self.user,
                tenant=self.tenant,
            )
            exc = deployment.make_create_environment_execution()
            exc.status = ExecutionState.TERMINATED
            node1 = self._node('vm', deployment=deployment)
            node2 = self._node('http_web_server', deployment=deployment)
            self._instance('vm_1', node=node1)
            self._instance('http_web_server_1', node=node2)
            deployments.append(deployment)
        return deployments

    def _put_n_snapshots(self, number_of_snapshots, prefix=None, suffix=None):
        prefix = prefix or 'oh-snap'
        suffix = suffix or ''
        for i in range(number_of_snapshots):
            self.client.snapshots.create(
                snapshot_id='{0}{1}{2}'.format(prefix, i, suffix),
                include_metrics=False,
                include_credentials=False
            )

    def _put_n_secrets(self, number_of_secrets):
        for i in range(number_of_secrets):
            self.client.secrets.create('test{0}_secret'.format(i), 'value')

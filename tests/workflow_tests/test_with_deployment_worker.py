########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'dank'


from cosmo_manager_rest_client.cosmo_manager_rest_client \
    import CosmoManagerRestClient

from testenv import TestCase
from testenv import get_resource as resource
from testenv import MANAGEMENT_NODE_ID as MANAGEMENT
from testenv import CLOUDIFY_WORKFLOWS_QUEUE as WORKFLOWS

from plugins.plugin_installer.tasks import get_installed_plugins
from plugins.worker_installer.tasks import (get_current_worker_state,
                                            RESTARTED,
                                            STARTED,
                                            INSTALLED,
                                            STOPPED,
                                            UNINSTALLED)

DEPLOYMENT = 'deployment_id'

AFTER_INSTALL_STAGES = [INSTALLED, STARTED, RESTARTED]
AFTER_UNINSTALL_STAGES = AFTER_INSTALL_STAGES + [STOPPED, UNINSTALLED]


class TestWitDeploymentWorker(TestCase):

    def setUp(self):
        super(TestWitDeploymentWorker, self).setUp()
        self.rest = CosmoManagerRestClient('localhost', port=8100)
        self._upload_and_deploy(resource('dsl/with_plugin.yaml'))
        self.node_id = self._list_nodes()[0].id
        self.deployment_worker = self.create_celery_worker(DEPLOYMENT)
        self.agent_worker = self.create_celery_worker(self.node_id)
        self.addCleanup(self.deployment_worker.close)
        self.addCleanup(self.agent_worker.close)
        self.agent_worker.start()
        self.deployment_worker.start()

    def test_dsl_with_agent_plugin_and_manager_plugin(self):
        self._execute('install')

        # test plugin installed in deployment worker
        deployment_plugins = self._get(get_installed_plugins, queue=DEPLOYMENT)
        self.assertIn('test_management_plugin', deployment_plugins)

        # test plugin installed in workflows worker
        workflow_plugin = self._get(get_installed_plugins, queue=WORKFLOWS)
        self.assertIn('workflow-default-plugin', workflow_plugin)

        # test plugins installed in agent worker
        agent_plugins = self._get(get_installed_plugins, queue=self.node_id)
        self.assertIn('test_plugin', agent_plugins)

        # test valid deployment worker installation order
        state = self._get(get_current_worker_state, queue=MANAGEMENT)
        self.assertEquals(state, AFTER_INSTALL_STAGES)

        # test valid workflows worker installation order
        # args=True will make it check the cloudify.workflows installation
        state = self._get(get_current_worker_state, queue=MANAGEMENT,
                          args=[True])
        self.assertEquals(state, AFTER_INSTALL_STAGES)

        # test valid agent worker installation order
        state = self._get(get_current_worker_state, queue=DEPLOYMENT)
        self.assertEquals(state, AFTER_INSTALL_STAGES)

        self._execute('uninstall')

        # test valid deployment worker un-installation order
        state = self._get(get_current_worker_state, queue=MANAGEMENT)
        self.assertEquals(state, AFTER_UNINSTALL_STAGES)

        # test valid workflows worker un-installation order
        # currently this is unimplemented
        # state = self._get(get_current_worker_state, queue=MANAGEMENT,
        #                   args=[True])
        # self.assertEquals(state, AFTER_UNINSTALL_STAGES)

        # test valid agent worker un-installation order
        # we do not call stop and uninstall on agent workers
        # state = self._get(get_current_worker_state, queue=DEPLOYMENT)
        # self.assertEquals(state, AFTER_UNINSTALL_STAGES)

    def _upload_and_deploy(self, dsl_path):
        blueprint_id = self.rest.publish_blueprint(dsl_path).id
        return self.rest.create_deployment(blueprint_id, DEPLOYMENT)

    def _execute(self, workflow):
        _, error = self.rest.execute_deployment(DEPLOYMENT,
                                                workflow,
                                                timeout=300)
        if error is not None:
            raise RuntimeError('Workflow execution failed: {}'.format(error))

    def _list_nodes(self):
        return self.rest.list_deployment_nodes(DEPLOYMENT).nodes

    def _get(self, task, queue, args=None):
        return self.send_task(task, queue=queue, args=args).get(timeout=10)

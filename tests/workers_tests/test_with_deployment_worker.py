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

import uuid
import time
import errno
from os import path


from workers_tests import WorkersTestCase
from testenv import get_resource as resource
from testenv import MANAGEMENT_NODE_ID as MANAGEMENT
from testenv import wait_for_execution_to_end
from testenv import send_task
from testenv import TestEnvironment
from testenv import do_retries
from testenv import verify_workers_installation_complete

from plugins.cloudmock.tasks import (
    setup_plugin_file_based_mode as setup_cloudmock,
    teardown_plugin_file_based_mode as teardown_cloudmock)
from plugins.plugin_installer.tasks import get_installed_plugins
from plugins.worker_installer.tasks import (
    get_worker_state,
    RESTARTED,
    STARTED,
    INSTALLED,
    STOPPED,
    UNINSTALLED)


BLUEPRINT_ID = str(uuid.uuid4())
DEPLOYMENT_ID = str(uuid.uuid4())
DEPLOYMENT_WORKFLOWS_QUEUE = '{0}_workflows'.format(DEPLOYMENT_ID)

AFTER_INSTALL_STAGES = [INSTALLED, STARTED, RESTARTED]
AFTER_UNINSTALL_STAGES = AFTER_INSTALL_STAGES + [STOPPED, UNINSTALLED]


class TestWithDeploymentWorker(WorkersTestCase):
    """
    This test is the only one (for the time this docstring was written)
    to test the real workers installation / un-installation workflows.
    """

    def setUp(self):
        super(TestWithDeploymentWorker, self).setUp()
        setup_cloudmock()

    def tearDown(self):
        teardown_cloudmock()
        super(TestWithDeploymentWorker, self).tearDown()

    def test_dsl_with_agent_plugin_and_manager_plugin(self):
        # start deployment workers
        deployment_worker = TestEnvironment.create_celery_worker(
            DEPLOYMENT_ID)
        self.addCleanup(deployment_worker.close)
        deployment_worker.start()

        deployment_workflows_worker = TestEnvironment.create_celery_worker(
            DEPLOYMENT_WORKFLOWS_QUEUE)
        self.addCleanup(deployment_workflows_worker.close)
        deployment_workflows_worker.start()

        # upload blueprint
        blueprint_id = self.client.blueprints.upload(
            resource('dsl/with_plugin.yaml'), BLUEPRINT_ID).id

        # create deployment
        self.client.deployments.create(blueprint_id, DEPLOYMENT_ID)

        # waiting for the deployment workers installation to complete
        do_retries(verify_workers_installation_complete, 15,
                   deployment_id=DEPLOYMENT_ID)

        # test plugin installed in deployment operations worker
        deployment_plugins = self._get(get_installed_plugins,
                                       queue=DEPLOYMENT_ID)

        self.assertIn('test_management_plugin', deployment_plugins)

        # test plugin installed in deployment workflows worker
        workflow_plugin = self._get(get_installed_plugins,
                                    queue=DEPLOYMENT_WORKFLOWS_QUEUE)
        self.assertIn('workflows', workflow_plugin)

        # test valid deployment worker installation order
        state = self._get(get_worker_state, queue=MANAGEMENT,
                          args=[DEPLOYMENT_ID])
        self.assertEquals(state, AFTER_INSTALL_STAGES)

        # test valid workflows worker installation order
        state = self._get(get_worker_state, queue=MANAGEMENT,
                          args=[DEPLOYMENT_WORKFLOWS_QUEUE])
        self.assertEquals(state, AFTER_INSTALL_STAGES)

        # test riemann core started successfully
        self.assertTrue(self._is_riemann_core_up())

        # start agent worker
        node_id = self._list_nodes()[0].id
        agent_worker = TestEnvironment.create_celery_worker(node_id)
        self.addCleanup(agent_worker.close)
        agent_worker.start()

        # install
        self._execute('install')

        # test plugins installed in agent worker
        agent_plugins = self._get(get_installed_plugins, queue=node_id)
        self.assertIn('test_plugin', agent_plugins)

        # test valid agent worker installation order
        state = self._get(get_worker_state, queue=DEPLOYMENT_ID,
                          args=[node_id])
        self.assertEquals(state, AFTER_INSTALL_STAGES)

        # uninstall
        self._execute('uninstall')

        # delete deployment
        self.client.deployments.delete(DEPLOYMENT_ID)

        # test valid deployment worker un-installation order
        state = self._get(get_worker_state, queue=MANAGEMENT,
                          args=[DEPLOYMENT_ID])
        self.assertEquals(state, AFTER_UNINSTALL_STAGES)

        # test valid workflows worker un-installation order
        state = self._get(get_worker_state, queue=MANAGEMENT,
                          args=[DEPLOYMENT_WORKFLOWS_QUEUE])
        self.assertEquals(state, AFTER_UNINSTALL_STAGES)

        # test valid agent worker un-installation order
        state = self._get(get_worker_state, queue=DEPLOYMENT_ID,
                          args=[node_id])
        self.assertEquals(state, AFTER_UNINSTALL_STAGES)

        # validate riemann core is no longer running
        self.assertFalse(self._is_riemann_core_up())

    def _execute(self, workflow):
        execution = self.client.deployments.execute(DEPLOYMENT_ID, workflow)
        wait_for_execution_to_end(execution)
        time.sleep(3)  # wait for execution status to update in elasticsearch

    def _list_nodes(self):
        return self.client.node_instances.list(deployment_id=DEPLOYMENT_ID)

    def _get(self, task, queue, args=None):
        return send_task(task, queue=queue, args=args).get(timeout=10)

    def _is_riemann_core_up(self):
        try:
            with open(path.join(self.riemann_workdir,
                                DEPLOYMENT_ID, 'ok')) as f:
                return f.read().strip() == 'ok'
        except IOError, e:
            if e.errno == errno.ENOENT:
                return False
            raise

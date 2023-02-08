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

import uuid
import time
import pytest
import tempfile

import yaml
from retrying import retry

from integration_tests.tests import utils
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import upload_mock_plugin

pytestmark = pytest.mark.group_general


@pytest.mark.usefixtures('cloudmock_plugin')
@pytest.mark.usefixtures('target_aware_mock_plugin')
class TestHooks(AgentlessTestCase):
    HOOKS_CONFIG_PATH = '/opt/mgmtworker/config/hooks.conf'
    LOG_PATH = '/var/log/cloudify/mgmtworker/mgmtworker.log'
    PLUGIN_LOG_PATH = '/tmp/hook_task.txt'

    def tearDown(self):
        self.env.execute_on_manager(['rm', '-f', self.PLUGIN_LOG_PATH])

    def test_missing_compatible_hook(self):
        new_config = """
hooks:
  - event_type: test_event_type
    implementation: package.module.task
    inputs:
      input1: bla
      input2: bla
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        workflow_started_msg = "received `workflow_started` event but " \
                               "didn't find a compatible hook"
        workflow_succeeded_msg = "received `workflow_succeeded` event but " \
                                 "didn't find a compatible hook"
        self._assert_messages_in_log([workflow_started_msg,
                                      workflow_succeeded_msg])

    def test_invalid_implementation_module(self):
        new_config = """
hooks:
  - event_type: workflow_started
    implementation: package.module.task
    inputs:
      input1: bla
      input2: bla
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        invalid_implementation_msg = "No module named package.module"
        self._assert_messages_in_log([invalid_implementation_msg])

    def test_invalid_implementation_task(self):
        new_config = """
hooks:
  - event_type: workflow_started
    implementation: cloudmock.cloudmock.tasks.test
    inputs:
      input1: bla
      input2: bla
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        invalid_task_msg = "cloudmock.tasks has no function named \\'test\\'"
        time.sleep(2)   # so that the mgmtworker log has time to refresh
        self._assert_messages_in_log([invalid_task_msg])

    def test_missing_implementation(self):
        new_config = """
hooks:
  - event_type: workflow_started
    inputs:
      input1: bla
      input2: bla
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        error_msg = "The hook consumer received `workflow_started` event and" \
                    " the hook implementation is: `None`"
        workflow_succeeded_msg = "received `workflow_succeeded` event but " \
                                 "didn't find a compatible hook"
        self._assert_messages_in_log([error_msg,
                                      workflow_succeeded_msg])

    def test_missing_inputs(self):
        new_config = """
hooks:
  - event_type: workflow_started
    implementation: cloudmock.tasks.hook_task
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        event_type_msg = "workflow_started"
        kwargs_msg = "kwargs: {}"
        self._assert_messages_in_log([event_type_msg, kwargs_msg],
                                     log_path=self.PLUGIN_LOG_PATH)

    def test_missing_hooks_key(self):
        new_config = """
test_hook:
    invalid: true
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        workflow_started_msg = "received `workflow_started` event but " \
                               "didn't find a compatible hook"
        workflow_succeeded_msg = "received `workflow_succeeded` event but " \
                                 "didn't find a compatible hook"
        self._assert_messages_in_log([workflow_started_msg,
                                      workflow_succeeded_msg])

    def test_missing_hooks_config(self):
        self.delete_manager_file(self.HOOKS_CONFIG_PATH)
        self._start_a_workflow()
        workflow_started_msg = "The hook consumer received " \
                               "`workflow_started` event but the " \
                               "hooks config file doesn't exist"
        workflow_succeeded_msg = "The hook consumer received " \
                                 "`workflow_succeeded` event but the " \
                                 "hooks config file doesn't exist"
        self._assert_messages_in_log([workflow_started_msg,
                                      workflow_succeeded_msg])

    def test_hook_config_invalid_yaml(self):
        new_config = """
        test_hook
            invalid: true
"""

        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write(new_config)
            f.flush()
            self.env.copy_file_to_manager(source=f.name,
                                          target=self.HOOKS_CONFIG_PATH,
                                          owner='cfyuser:')

        self._start_a_workflow()
        workflow_started_error = "ERROR - The hook consumer received " \
                                 "`workflow_started` event but the hook " \
                                 "config file is invalid yaml"
        workflow_succeeded_error = "ERROR - The hook consumer received " \
                                   "`workflow_succeeded` event but the " \
                                   "hook config file is invalid yaml"
        self._assert_messages_in_log([workflow_started_error,
                                      workflow_succeeded_error])

    def test_default_hook_config(self):
        self._start_a_workflow()
        workflow_started_msg = "received `workflow_started` event but " \
                               "didn't find a compatible hook"
        workflow_succeeded_msg = "received `workflow_succeeded` event but " \
                                 "didn't find a compatible hook"
        self._assert_messages_in_log([workflow_started_msg,
                                      workflow_succeeded_msg])

    def test_implementation_plugin(self):
        new_config = """
hooks:
  - event_type: workflow_started
    implementation: target_aware_mock.target_aware_mock.tasks.hook_task
    inputs:
      input1: input1_test
      input2: input2_test
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        event_type_msg = "workflow_started"
        workflow_id_msg = "create_deployment_environment"
        input1_msg = "input1_test"
        messages = [event_type_msg, workflow_id_msg, input1_msg]
        self._assert_messages_in_log(messages, log_path=self.PLUGIN_LOG_PATH)

    def test_different_plugin_versions(self):
        new_config = """
    hooks:
      - event_type: workflow_started
        implementation: target_aware_mock.target_aware_mock.tasks.hook_task
        inputs:
          input1: input1_test
          input2: input2_test
        description: test hook
    """
        old_version = '1.0'
        new_version = '1.33'

        upload_mock_plugin(self.client, 'target-aware-mock-v1_33', new_version)

        self._update_hooks_config(new_config)
        self._start_a_workflow()
        event_type_msg = "workflow_started"
        workflow_id_msg = "create_deployment_environment"
        input1_msg = "input1_test"

        # Verify that the hook task calls the newest version of the plugin
        newest_version_msg = "version 1.33"
        messages = [event_type_msg,
                    workflow_id_msg,
                    input1_msg,
                    newest_version_msg]
        self._assert_messages_in_log(messages,
                                     log_path=self.PLUGIN_LOG_PATH)

        # Verify that both versions of the plugin are installed on manager
        versions = [plugin['package_version'] for plugin in
                    self.client.plugins.list(
                    package_name='target_aware_mock').items]
        assert (old_version in versions) and (new_version in versions)

    def test_implementation_function(self):
        new_config = """
hooks:
  - event_type: workflow_started
    implementation: cloudify.tests.mocks.mock_module.mock_hook_function
    inputs:
      input1: input1_test
      input2: input2_test
    description: test hook
"""
        self._update_hooks_config(new_config)
        tokens_before = self.client.tokens.list().metadata.pagination['total']
        self._start_a_workflow()
        event_type_msg = "workflow_started"
        workflow_id_msg = "create_deployment_environment"
        input1_msg = "input1_test"
        input2_msg = "input2_test"
        messages = [event_type_msg, workflow_id_msg, input1_msg, input2_msg]
        self._assert_messages_in_log(messages,
                                     log_path='/tmp/mock_hook_function.txt')
        tokens_after = self.client.tokens.list().metadata.pagination['total']
        assert tokens_before == tokens_after

    def test_multiple_hooks(self):
        new_config = """
hooks:
  - event_type: workflow_started
    implementation: cloudify.tests.mocks.mock_module.mock_hook_function
    inputs:
      input1: input1_workflow_started
      input2: input2_workflow_started
    description: test hook
  - event_type: workflow_succeeded
    implementation: cloudify.tests.mocks.mock_module.mock_hook_function
    inputs:
      input1: input1_workflow_succeeded
      input2: input2_workflow_succeeded
    description: test hook
  - event_type: workflow_failed
    implementation: cloudify.tests.mocks.mock_module.mock_hook_function
    inputs:
      input1: input1_workflow_failed
      input2: input2_workflow_failed
    description: test hook
"""
        self._update_hooks_config(new_config)
        self._start_a_workflow()
        started_event_type_msg = "workflow_started"
        succeeded_event_type_msg = "workflow_succeeded"
        workflow_id_msg = "create_deployment_environment"
        started_kwargs_msg = "input1_workflow_started"
        succeeded_kwargs_msg = "input2_workflow_succeeded"
        messages = [started_event_type_msg, succeeded_event_type_msg,
                    workflow_id_msg, started_kwargs_msg, succeeded_kwargs_msg]
        self._assert_messages_in_log(messages,
                                     log_path='/tmp/mock_hook_function.txt')

    def _start_a_workflow(self):
        # Start the create deployment workflow
        dsl_path = utils.get_resource('dsl/basic.yaml')
        blueprint_id = deployment_id = 'basic_{}'.format(uuid.uuid4())
        self.client.blueprints.upload(dsl_path, blueprint_id)
        utils.wait_for_blueprint_upload(blueprint_id, self.client)
        self.client.deployments.create(blueprint_id,
                                       deployment_id)
        utils.wait_for_deployment_creation_to_complete(
            self.env,
            deployment_id,
            self.client
        )
        return deployment_id

    @retry(wait_fixed=1000, stop_max_attempt_number=3)
    def _assert_messages_in_log(self, messages, log_path=LOG_PATH):
        tmp_log_path = str(self.workdir / 'test_log')
        try:
            self.env.copy_file_from_manager(log_path, tmp_log_path)
        except Exception:
            return
        with open(tmp_log_path) as f:
            data = f.readlines()
        last_log_lines = str(data[-20:])
        for message in messages:
            assert message in last_log_lines

    def _update_hooks_config(self, new_config):
        with tempfile.NamedTemporaryFile(mode='w') as f:
            yaml.dump(yaml.safe_load(new_config), f, default_flow_style=False)
            f.flush()
            self.env.copy_file_to_manager(source=f.name,
                                          target=self.HOOKS_CONFIG_PATH,
                                          owner='cfyuser:')

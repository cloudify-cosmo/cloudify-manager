#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from unittest import TestCase

from cloudify_system_workflows.deployment_environment import (
    _merge_deployment_and_workflow_plugins as merge_plugins)


class TestDeploymentPluginsInstallation(TestCase):

    def test_empty_plugin_lists(self):
        dep_plugins = []
        wf_plugins = []
        self.assertEqual([], merge_plugins(deployment_plugins=dep_plugins,
                                           workflow_plugins=wf_plugins))

    def test_empty_dep_plugin_list(self):
        dep_plugins = []
        wf_plugins = [{'name': 'one'}]
        self.assertEqual([{'name': 'one'}],
                         merge_plugins(deployment_plugins=dep_plugins,
                                       workflow_plugins=wf_plugins))

    def test_empty_workflow_plugin_list(self):
        dep_plugins = [{'name': 'one'}]
        wf_plugins = []
        self.assertEqual([{'name': 'one'}],
                         merge_plugins(deployment_plugins=dep_plugins,
                                       workflow_plugins=wf_plugins))

    def test_no_duplicate_plugin_lists(self):
        dep_plugins = [{'name': 'one'}]
        wf_plugins = [{'name': 'two'}]
        self.assertEqual([{'name': 'one'}, {'name': 'two'}],
                         merge_plugins(deployment_plugins=dep_plugins,
                                       workflow_plugins=wf_plugins))

    def test_plugin_lists_with_duplicates(self):
        dep_plugins = [{'name': 'one'}]
        wf_plugins = [{'name': 'one'}]
        self.assertEqual([{'name': 'one'}],
                         merge_plugins(deployment_plugins=dep_plugins,
                                       workflow_plugins=wf_plugins))

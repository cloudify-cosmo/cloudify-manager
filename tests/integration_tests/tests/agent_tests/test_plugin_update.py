########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import uuid
import shutil
import pytest

from functools import wraps

import integration_tests_plugins

from integration_tests import AgentTestWithPlugins
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_blueprint_upload,
    wait_for_deployment_creation_to_complete
)
from integration_tests.framework.utils import zip_files

pytestmark = pytest.mark.group_plugins


def setup_for_sourced_plugins(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'
        self.plugin_name = 'version_aware'
        self.plugin_dir_name_prefix = self.plugin_name + '_'
        self.base_name = 'base_sourced'
        self.base_blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.mod_name = 'mod_sourced'
        self.mod_blueprint_id = 'b{0}'.format(uuid.uuid4())

        self.addCleanup(self._remove_files)
        self._prepare_files()
        return f(self, *args, **kwargs)

    return wrapper


def setup_for_plugins_update(f):
    @pytest.mark.usefixtures('version_aware_plugin')
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        self.blueprint_name_prefix = 'plugins_update'
        self.base_blueprint_id = 'b{0}'.format(uuid.uuid4())
        _f = uploads_mock_plugins(f)
        return _f(self, *args, **kwargs)

    return wrapper


def uploads_mock_plugins(f):
    @pytest.mark.usefixtures('version_aware_plugin')
    @pytest.mark.usefixtures('version_aware_v2_plugin')
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        self.addCleanup(self._clear_managed_plugins)
        return f(self, *args, **kwargs)

    return wrapper


class TestPluginUpdate(AgentTestWithPlugins):
    versions = ['1.0', '2.0']
    dsl_resources_path = resource(os.path.join('dsl', 'agent_tests'))
    blueprint_name_prefix = 'plugin_update_'
    setup_deployment_ids = None

    @pytest.mark.xfail  # RD-3911
    @uploads_mock_plugins
    def test_plugin_update(self):
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'
        self.plugin_name = 'version_aware'
        self.base_name = 'base'
        self.base_blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.mod_name = 'mod'
        self.mod_blueprint_id = 'b{0}'.format(uuid.uuid4())

        self._upload_blueprints_and_deploy_base()

        # Execute base (V 1.0) workflows
        self._execute_workflows()
        self._assert_on_values(self.versions[0])

        self._perform_update()

        # Execute mod (V 2.0) workflows
        self._execute_workflows()
        self._assert_on_values(self.versions[1])

    @uploads_mock_plugins
    def test_host_agent_plugin_update(self):
        def execute_host_op():
            execution = self.client.executions.start(
                self.setup_deployment_id,
                'execute_operation',
                parameters={
                    'operation': 'test_host.host_op',
                    'node_ids': ['node']
                })
            self.wait_for_execution_to_end(execution)
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'
        self.plugin_name = 'version_aware'
        self.base_name = 'host_agent'
        self.base_blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.mod_name = 'host_agent_mod'
        self.mod_blueprint_id = 'b{0}'.format(uuid.uuid4())

        self._upload_blueprints_and_deploy_base()

        # Execute base (V 1.0) workflows
        execute_host_op()
        self._assert_host_values(self.versions[0])

        self._perform_update()

        # Execute mod (V 2.0) workflows
        execute_host_op()
        self._assert_host_values(self.versions[1])

    @setup_for_sourced_plugins
    def test_sourced_plugin_updates(self):
        self._upload_blueprints_and_deploy_base()

        # Execute base (V 1.0) workflows
        self._execute_workflows()
        self._assert_on_values(self.versions[0])

        self._perform_update()

        # Execute mod (V 2.0) workflows
        self._execute_workflows()
        self._assert_on_values(self.versions[1])

    @setup_for_plugins_update
    def test_single_deployment_is_updated(self):
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'
        self.plugin_name = 'version_aware'

        self.deploy_application(
            dsl_path=self._get_dsl_blueprint_path(''),
            blueprint_id=self.base_blueprint_id,
            deployment_id=self.setup_deployment_id
        )
        self._upload_v_2_plugin()

        # Execute base (V 1.0) workflows
        self._execute_workflows()
        self._assert_host_values(self.versions[0])

        plugins_update = self._perform_plugins_update()
        self.assertEqual(plugins_update.state, 'successful')

        # Execute mod (V 2.0) workflows
        self._execute_workflows()
        self._assert_host_values(self.versions[1])

        plugins_update = self._perform_plugins_update()
        self.assertEqual(plugins_update.state, 'no_changes_required')

        # Execute mod (V 2.0) workflows
        self._execute_workflows()
        self._assert_host_values(self.versions[1])

    @setup_for_plugins_update
    def test_many_deployments_are_updated(self):
        self.setup_deployment_ids = ['d{0}'.format(uuid.uuid4())
                                     for _ in range(5)]
        self.setup_node_id = 'node'
        self.plugin_name = 'version_aware'

        self.client.blueprints.upload(
            path=self._get_dsl_blueprint_path(''),
            entity_id=self.base_blueprint_id)
        wait_for_blueprint_upload(self.base_blueprint_id, self.client)
        blueprint = self.client.blueprints.get(self.base_blueprint_id)
        for dep_id in self.setup_deployment_ids:
            self.client.deployments.create(blueprint.id, dep_id)
            wait_for_deployment_creation_to_complete(
                self.env.container_id,
                dep_id,
                self.client
            )
            self.execute_workflow('install', dep_id)
        self._upload_v_2_plugin()

        # Execute base (V 1.0) workflows
        for dep_id in self.setup_deployment_ids:
            self.setup_deployment_id = dep_id
            self._execute_workflows()
            self._assert_host_values(self.versions[0])

        plugins_update = self._perform_plugins_update()
        self.assertEqual(plugins_update.state, 'successful')

        # Execute mod (V 2.0) workflows
        for dep_id in self.setup_deployment_ids:
            self.setup_deployment_id = dep_id
            self._execute_workflows()
            self._assert_host_values(self.versions[1])

    @setup_for_plugins_update
    def test_additional_constraints(self):
        self.setup_deployment_id = 'd{0}'.format(uuid.uuid4())
        self.setup_node_id = 'node'
        self.plugin_name = 'version_aware'

        self.deploy_application(
            dsl_path=self._get_dsl_blueprint_path(''),
            blueprint_id=self.base_blueprint_id,
            deployment_id=self.setup_deployment_id
        )
        self._upload_v_2_plugin()

        # Execute base (V 1.0) workflows
        self._execute_workflows()
        self._assert_host_values(self.versions[0])

        # Update a different (non-existent) plugin - nothing should change
        plugins_update = self._perform_plugins_update(plugin_names=['asd'])
        self.assertEqual(plugins_update.state, 'no_changes_required')
        self._execute_workflows()
        self._assert_host_values(self.versions[0])

        # Update only minor version - nothing should change
        plugins_update = self._perform_plugins_update(all_to_minor=True,
                                                      all_to_latest=False)
        self.assertEqual(plugins_update.state, 'no_changes_required')
        self._execute_workflows()
        self._assert_host_values(self.versions[0])

        # This should do the update
        plugins_update = self._perform_plugins_update(
            to_latest=[self.plugin_name])
        self.assertEqual(plugins_update.state, 'successful')
        self._execute_workflows()
        self._assert_host_values(self.versions[1])

    def _perform_plugins_update(self, **kwargs):
        plugins_update = self.client.plugins_update.update_plugins(
            self.base_blueprint_id, **kwargs)
        execution_id = plugins_update.execution_id
        execution = self.client.executions.get(execution_id)
        self.wait_for_execution_to_end(execution)
        return self.client.plugins_update.get(plugins_update.id)

    def _prepare_files(self):
        # Copy v1.0 twice to different directories
        source_dir = self._get_source_dir_for_plugin()
        self._copy_plugin_files_to_resources(source_dir, self.versions[0])
        target_dir = self._copy_plugin_files_to_resources(source_dir,
                                                          self.versions[1])
        # Replace 1.0 strings with 2.0
        self._replace_version(target_dir, *self.versions)

    def _copy_plugin_files_to_resources(self, source_dir, version):
        target_dir = os.path.join(self.dsl_resources_path,
                                  'plugins',
                                  self.plugin_dir_name_prefix + version)
        if not os.path.exists(target_dir):
            shutil.copytree(source_dir, target_dir)
        return target_dir

    def _remove_files(self):
        for version in self.versions:
            dir_to_rm = os.path.join(
                self.dsl_resources_path,
                'plugins',
                self.plugin_dir_name_prefix + version)
            shutil.rmtree(dir_to_rm, ignore_errors=True)

    def _perform_update(self, update_plugins=True):
        execution_id = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment_id=self.setup_deployment_id,
                blueprint_id=self.mod_blueprint_id,
                update_plugins=update_plugins
            ).execution_id
        execution = self.client.executions.get(execution_id)
        self.wait_for_execution_to_end(execution)

    def _get_work_dir_for_plugin(self):
        return str(self.workdir / self.plugin_name)

    def _get_source_dir_for_plugin(self):
        plugins_dir = os.path.dirname(integration_tests_plugins.__file__)
        return os.path.join(plugins_dir, self.plugin_name)

    def _copy_plugin_files_to_work_dir(self):
        source_dir = self._get_source_dir_for_plugin()
        target_dir = self._get_work_dir_for_plugin()
        if not os.path.exists(target_dir):
            shutil.copytree(source_dir, target_dir)
        return target_dir

    def _upload_v_2_plugin(self):
        plugin_name = 'version_aware_v2'
        plugins_dir = os.path.dirname(integration_tests_plugins.__file__)
        plugin_source = os.path.join(plugins_dir, plugin_name)

        wagon_paths = self._get_or_create_wagon(plugin_source)
        for wagon_path in wagon_paths:
            yaml_path = os.path.join(plugin_source, 'plugin.yaml')
            with zip_files([wagon_path, yaml_path]) as zip_path:
                self.client.plugins.upload(zip_path, visibility='global')
        self.logger.info(
            'Finished uploading {0}...'.format(plugin_name))

    @staticmethod
    def _replace_version(target_dir, v1, v2):
        """ https://stackoverflow.com/a/4205918/978089 """

        for dname, dirs, files in os.walk(target_dir):
            for fname in files:
                fpath = os.path.join(dname, fname)
                with open(fpath) as f:
                    s = f.read()
                s = s.replace(v1, v2)
                with open(fpath, 'w') as f:
                    f.write(s)

    def _assert_cda_values(self, version):
        cda_data = self.get_runtime_property(self.setup_deployment_id,
                                             'cda_op')
        self.assertEqual(len(cda_data), 1)
        self.assertEqual(cda_data[0], version)

    def _assert_host_values(self, version):
        host_data = self.get_runtime_property(self.setup_deployment_id,
                                              'host_op')
        self.assertEqual(len(host_data), 1)
        self.assertEqual(host_data[0], version)

    def _assert_on_values(self, version):
        self._assert_cda_values(version)
        self._assert_host_values(version)
        plugins = self.client.plugins.list(package_name='version_aware')
        if not plugins:
            return
        target_plugin = next(p for p in plugins
                             if p.package_version == version)
        other_plugins = [p for p in plugins if p.package_version != version]

        assert all(pstate['state'] == 'installed'
                   for pstate in target_plugin.installation_state)
        for other_plugin in other_plugins:
            assert all(pstate['state'] != 'installed'
                       for pstate in other_plugin.installation_state)

    def _upload_blueprints_and_deploy_base(self):
        self.deploy_application(
            dsl_path=self._get_dsl_blueprint_path(self.base_name),
            blueprint_id=self.base_blueprint_id,
            deployment_id=self.setup_deployment_id
        )

        self.client.blueprints.upload(
            path=self._get_dsl_blueprint_path(self.mod_name),
            entity_id=self.mod_blueprint_id
        )
        wait_for_blueprint_upload(self.mod_blueprint_id, self.client)

    def _get_dsl_blueprint_path(self, name):
        plugin_path = '{0}{1}.yaml'.format(self.blueprint_name_prefix, name)
        return os.path.join(self.dsl_resources_path, plugin_path)

    def _execute_workflows(self):
        for wf in ('test_cda_wf', 'test_cda_op', 'test_host_op'):
            self.execute_workflow(wf, self.setup_deployment_id)

    def _clear_managed_plugins(self):
        plugins = self.client.plugins.list()
        plugin_name = getattr(self, 'plugin_name', None)
        if not plugin_name:
            return
        for p in plugins:
            if plugin_name in p.package_name:
                self.client.plugins.delete(p.id, force=True)
                self._wait_for_execution_by_wf_name('uninstall_plugin')

#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

import pytest

from cloudify.models_states import VisibilityState
from cloudify.constants import COMPONENT, SHARED_RESOURCE

from dsl_parser.constants import NODES, OUTPUTS, PROPERTIES

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource

pytestmark = pytest.mark.group_deployments

MAIN_DEPLOYMENT = 'main_deployment'
MAIN_BLUEPRINT_ID = 'main_blueprint'
MOD_BLUEPRINT_ID = 'mod_blueprint'
COMPUTE_NODE = 'compute_node'
SR_DEPLOYMENT = 'shared_resource_deployment'

# Dependencies creation test constants
CREATION_TEST_BLUEPRINT = 'dsl/idd/dependency_creating_resources.yaml'

# Deployment Update tests constants
SR_DEPLOYMENT1 = SR_DEPLOYMENT + '1'
SR_DEPLOYMENT2 = SR_DEPLOYMENT + '2'
COMP_DEPLOYMENT1 = 'single_component_deployment1'
COMP_DEPLOYMENT2 = 'single_component_deployment2'
BLUEPRINT_BASE = 'dsl/idd/inter_deployment_dependency_dep_base.yaml'
BLUEPRINT_MOD = 'dsl/idd/inter_deployment_dependency_dep_modified.yaml'


@pytest.mark.usefixtures('cloudmock_plugin')
class TestInterDeploymentDependenciesInfrastructure(AgentlessTestCase):

    def test_dependencies_are_created(self):
        self._assert_dependencies_count(0)
        self._prepare_creation_test_resources()
        dependencies = self._assert_dependencies_count(2)
        self._assert_initial_compute_node_dependencies(dependencies)

        self._install_main_deployment()
        node_instances = self.client.node_instances.list()
        shared_resource = self._get_shared_resource_instance(node_instances)
        components = [i for i in node_instances if 'component' in i.node_id]
        # 6 = 3 components + 1 shared resource + 2 get_capability functions
        dependencies = self._assert_dependencies_count(6)
        dependencies = self._get_dependencies_dict(dependencies)

        for component in components:
            target_deployment = \
                component.runtime_properties['deployment']['id']
            self._assert_dependency_exists(
                dependency_creator=self._get_component_dependency_creator(
                    component.id),
                target_deployment=target_deployment,
                dependencies=dependencies)
        self._assert_dependency_exists(
            dependency_creator=self._get_shared_resource_dependency_creator(
                shared_resource.id),
            target_deployment=SR_DEPLOYMENT,
            dependencies=dependencies)

        self._uninstall_main_deployment()
        dependencies = self._assert_dependencies_count(2)
        for dependency in dependencies:
            self.assertNotIn(COMPONENT, dependency.dependency_creator)
            self.assertNotIn(SHARED_RESOURCE, dependency.dependency_creator)

        self.delete_deployment(MAIN_DEPLOYMENT,
                               validate=True,
                               client=self.client)
        self._assert_dependencies_count(0)

    def test_dependencies_are_updated(self):
        self._test_dependencies_are_updated(skip_uninstall=False)

    def test_dependencies_are_updated_but_keeps_old_dependencies(self):
        self._test_dependencies_are_updated(skip_uninstall=True)

    def test_cyclic_dependency_after_execution(self):
        """Creating a cyclic dependency in a workflow, fails that execution.

        We'll prepare two deployments that will eventually depend on each
        other; having dep1 depend on dep2 is OK, but then making dep2
        depend on dep1, is going to fail the execution that attempted
        to set this dependency.
        """
        self.upload_blueprint_resource(
            'dsl/idd/dependency_from_property.yaml', 'bp1'
        )
        self.client.deployments.create(
            'bp1', 'dep1', inputs={'target_id': 'dep2'})
        self.client.deployments.create(
            'bp1', 'dep2', inputs={'target_id': 'dep1'})
        self.wait_for_deployment_environment('dep1')
        self.wait_for_deployment_environment('dep2')
        exc = self.client.executions.start(
            'dep1', 'execute_operation', parameters={
                'operation': 'custom.set_attribute',
            }
        )
        self.wait_for_execution_to_end(exc)

        outs = self.client.deployments.outputs.get('dep1')
        assert outs.outputs == {'out1': 1}

        exc = self.client.executions.start(
            'dep2', 'execute_operation', parameters={
                'operation': 'custom.set_attribute',
            }
        )
        with self.assertRaises(RuntimeError):
            self.wait_for_execution_to_end(exc)

    def _test_dependencies_are_updated(self, skip_uninstall):
        self._assert_dependencies_count(0)
        self._prepare_dep_update_test_resources()
        base_expected_dependencies = self._get_dep_update_test_dependencies(
            is_first_state=True)
        base_dependencies = self._assert_dependencies_count(
            len(base_expected_dependencies))

        self._assert_dependencies_exist(base_expected_dependencies,
                                        base_dependencies)

        self._perform_update_on_main_deployment(skip_uninstall=skip_uninstall)
        mod_expected_dependencies = self._get_dep_update_test_dependencies(
            is_first_state=False)
        mod_dependencies = self._assert_dependencies_count(
            len(mod_expected_dependencies))
        self._assert_dependencies_exist(mod_expected_dependencies,
                                        mod_dependencies)

        self.undeploy_application(MAIN_DEPLOYMENT, is_delete_deployment=True)
        self._assert_dependencies_count(0)

    def _uninstall_main_deployment(self):
        self.execute_workflow('uninstall', MAIN_DEPLOYMENT)

    def _perform_update_on_main_deployment(self, skip_uninstall=False):
        execution_id = \
            self.client.deployment_updates.update_with_existing_blueprint(
                deployment_id=MAIN_DEPLOYMENT,
                blueprint_id=MOD_BLUEPRINT_ID,
                skip_uninstall=skip_uninstall
            ).execution_id
        execution = self.client.executions.get(execution_id)
        self.wait_for_execution_to_end(execution)

    def _install_main_deployment(self):
        self.execute_workflow('install', MAIN_DEPLOYMENT)

    @staticmethod
    def _get_component_dependency_creator(component_instance_id):
        return '{0}.{1}'.format(COMPONENT, component_instance_id)

    @staticmethod
    def _get_shared_resource_dependency_creator(shared_resource_instance_id):
        return '{0}.{1}'.format(SHARED_RESOURCE, shared_resource_instance_id)

    def _assert_dependencies_count(self, amount):
        dependencies = self.client.inter_deployment_dependencies.list()
        self.assertEqual(amount, len(dependencies))
        return dependencies

    def _prepare_creation_test_resources(self):
        self.client.secrets.create(SR_DEPLOYMENT + '_key',
                                   SR_DEPLOYMENT)
        self._deploy_shared_resource()
        self._upload_component_blueprint()
        self._deploy_main_deployment(CREATION_TEST_BLUEPRINT)

    def _upload_component_blueprint(self):
        self.upload_blueprint_resource('dsl/basic.yaml',
                                       'component_blueprint',
                                       client=self.client)

    def _prepare_dep_update_test_resources(self):
        self.client.secrets.create(SR_DEPLOYMENT1 + '_key',
                                   SR_DEPLOYMENT1)
        self.client.secrets.create(SR_DEPLOYMENT2 + '_key',
                                   SR_DEPLOYMENT2)
        self._deploy_shared_resource(SR_DEPLOYMENT1)

        self._deploy_shared_resource(
            SR_DEPLOYMENT2,
            upload_blueprint=False,
            resource_visibility=VisibilityState.PRIVATE)

        self._upload_component_blueprint()
        self.upload_blueprint_resource(BLUEPRINT_MOD,
                                       MOD_BLUEPRINT_ID,
                                       client=self.client)
        self._deploy_main_deployment(BLUEPRINT_BASE)
        self._install_main_deployment()

    def _deploy_main_deployment(self, blueprint_path):
        main_blueprint = get_resource(blueprint_path)
        self.deploy(main_blueprint, MAIN_BLUEPRINT_ID, 'main_deployment')

    def _deploy_shared_resource(self,
                                deployment_id=SR_DEPLOYMENT,
                                upload_blueprint=True,
                                resource_visibility=VisibilityState.GLOBAL):
        shared_resource_blueprint = get_resource(
            'dsl/blueprint_with_capabilities.yaml')
        self.deploy(shared_resource_blueprint if upload_blueprint else None,
                    'shared_resource_blueprint',
                    deployment_id,
                    blueprint_visibility=resource_visibility,
                    deployment_visibility=resource_visibility)

    def _assert_dependency_exists(self,
                                  dependency_creator,
                                  target_deployment,
                                  dependencies):
        self.assertIn(dependency_creator, dependencies)
        dependency = dependencies[dependency_creator]
        self.assertEqual(MAIN_DEPLOYMENT, dependency.source_deployment_id)
        self.assertEqual(
            target_deployment,
            dependency.target_deployment_id,
            msg='Target deployment of dependency creator {0} with the value '
                '{1} is not equal to the expected value {2}'
                ''.format(dependency_creator,
                          dependency.target_deployment_id,
                          target_deployment))

    def _assert_initial_compute_node_dependencies(self,
                                                  dependencies):
        for dependency in dependencies:
            self.assertEqual(dependency.source_deployment_id, MAIN_DEPLOYMENT)
            if 'property_static' in dependency.dependency_creator:
                self.assertEqual(dependency.target_deployment_id,
                                 SR_DEPLOYMENT)
            elif 'property_function' in dependency.dependency_creator:
                self.assertEqual(dependency.target_deployment_id,
                                 SR_DEPLOYMENT)
                secret_func = {'get_secret': 'shared_resource_deployment_key'}
                self.assertEqual(dependency['target_deployment_func'],
                                 secret_func)
            else:
                self.fail('Unexpected dependency creator "{0}"'
                          ''.format(dependency.dependency_creator))

    def _assert_dependencies_exist(self,
                                   dependencies_to_check,
                                   current_dependencies):
        creator_to_dependency = self._get_dependencies_dict(
            current_dependencies)
        for dependency_creator, target_deployment \
                in dependencies_to_check.items():
            self._assert_dependency_exists(
                dependency_creator,
                target_deployment,
                creator_to_dependency)

    def _get_dep_update_test_dependencies(self,
                                          is_first_state):
        shared_deployment_target = SR_DEPLOYMENT1
        comp_target_id = COMP_DEPLOYMENT1
        if not is_first_state:
            shared_deployment_target = SR_DEPLOYMENT2
            comp_target_id = COMP_DEPLOYMENT2
        node_instances = self.client.node_instances.list()
        shared_resource = self._get_shared_resource_instance(
            node_instances)
        component = self._get_component_instance(node_instances)
        dependencies = {
            '{0}.{1}.{2}.static_changed_to_static.get_capability'
            ''.format(NODES, COMPUTE_NODE, PROPERTIES):
                shared_deployment_target,
            '{0}.{1}.{2}.static_changed_to_function.get_capability'
            ''.format(NODES, COMPUTE_NODE, PROPERTIES):
                shared_deployment_target,
            '{0}.{1}.{2}.function_changed_to_function.get_capability'
            ''.format(NODES, COMPUTE_NODE, PROPERTIES):
                shared_deployment_target,
            '{0}.{1}.{2}.function_changed_to_static.get_capability'
            ''.format(NODES, COMPUTE_NODE, PROPERTIES):
                shared_deployment_target,
            '{0}.static_changed_to_static.value.get_capability'
            ''.format(OUTPUTS):
                shared_deployment_target,
            '{0}.static_changed_to_function.value.get_capability'
            ''.format(OUTPUTS):
                shared_deployment_target,
            '{0}.function_changed_to_function.value.get_capability'
            ''.format(OUTPUTS):
                shared_deployment_target,
            '{0}.function_changed_to_static.value.get_capability'
            ''.format(OUTPUTS):
                shared_deployment_target,
            self._get_shared_resource_dependency_creator(
                shared_resource.id):
                shared_deployment_target,
            self._get_component_dependency_creator(component.id):
                comp_target_id,
        }

        if is_first_state:
            dependencies['{0}.{1}.{2}.might_be_deleted.get_capability'
                         ''.format(NODES, COMPUTE_NODE, PROPERTIES)] = \
                SR_DEPLOYMENT1

        if is_first_state:
            dependencies['{0}.should_be_deleted.value.get_capability'
                         ''.format(OUTPUTS)] = SR_DEPLOYMENT1
        else:

            dependencies.update({
                '{0}.should_be_created_static.value.get_capability'
                ''.format(OUTPUTS):
                    SR_DEPLOYMENT2,
                '{0}.should_be_created_function.value.get_capability'
                ''.format(OUTPUTS):
                    SR_DEPLOYMENT2,
                '{0}.{1}.{2}.should_be_created_static.get_capability'
                ''.format(NODES, COMPUTE_NODE, PROPERTIES):
                    SR_DEPLOYMENT2,
                '{0}.{1}.{2}.should_be_created_function.get_capability'
                ''.format(NODES, COMPUTE_NODE, PROPERTIES):
                    SR_DEPLOYMENT2,
            })

        return dependencies

    @staticmethod
    def _get_shared_resource_instance(node_instances):
        return [i for i in node_instances
                if 'shared_resource_node' == i.node_id][0]

    @staticmethod
    def _get_component_instance(node_instances):
        return [i for i in node_instances
                if 'single_component_node' == i.node_id][0]

    @staticmethod
    def _get_dependencies_dict(dependencies_list):
        return {dependency.dependency_creator: dependency
                for dependency in dependencies_list}

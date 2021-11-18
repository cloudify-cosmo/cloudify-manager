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

import os

from cloudify.models_states import VisibilityState
from cloudify_rest_client.exceptions import CloudifyClientError

from .test_base import SecurityTestBase


class ResourcePermissionTests(SecurityTestBase):
    NOT_FOUND_MSG = '404: Requested `{0}` with ID `{1}` was not found'

    def _upload_blueprint(self, visibility=VisibilityState.TENANT):
        blueprint_id = 'blueprint_id'
        blueprint_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            'blueprint.yaml'
        )
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            self.client.blueprints.upload(
                blueprint_path,
                blueprint_id,
                visibility=visibility,
                async_upload=True
            )
            # parse plan on rest service side
            self.execute_upload_blueprint_workflow(blueprint_id)

        return blueprint_id

    def _create_deployment(self, visibility=VisibilityState.TENANT):
        deployment_id = 'deployment_id'
        blueprint_id = self._upload_blueprint()
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            self.client.deployments.create(blueprint_id,
                                           deployment_id,
                                           visibility=visibility)
        return deployment_id

    def _upload_plugin(self, visibility=VisibilityState.TENANT):
        plugin_path = self.create_wheel('psutil', '3.3.0')

        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            plugin = self.client.plugins.upload(plugin_path,
                                                visibility=visibility)
        return plugin.id

    def test_private_blueprint(self):
        blueprint_id = self._upload_blueprint(VisibilityState.PRIVATE)
        self._test_resource_get_and_list(
            resource_name='Blueprint',
            get_func_getter=lambda client: client.blueprints.get,
            resource_id=blueprint_id,
            list_func_getter=lambda client: client.blueprints.list
        )

    def test_private_deployment(self):
        deployment_id = self._create_deployment(VisibilityState.PRIVATE)
        self._test_resource_get_and_list(
            resource_name='Deployment',
            get_func_getter=lambda client: client.deployments.get,
            resource_id=deployment_id,
            list_func_getter=lambda client: client.deployments.list
        )

    def test_private_plugin(self):
        plugin_id = self._upload_plugin(VisibilityState.PRIVATE)
        self._test_resource_get_and_list(
            resource_name='Plugin',
            get_func_getter=lambda client: client.plugins.get,
            resource_id=plugin_id,
            list_func_getter=lambda client: client.plugins.list
        )

    def test_cant_view_private_blueprint(self):
        blueprint_id = self._upload_blueprint(VisibilityState.PRIVATE)
        self._test_cant_view_private_resource(
            resource_id=blueprint_id,
            resource_name='Blueprint',
            get_func_getter=lambda client: client.blueprints.get
        )

    def test_cant_view_private_plugin(self):
        plugin_id = self._upload_plugin(VisibilityState.PRIVATE)
        self._test_cant_view_private_resource(
            resource_id=plugin_id,
            resource_name='Plugin',
            get_func_getter=lambda client: client.plugins.get
        )

    def test_cant_view_private_deployment(self):
        deployment_id = self._create_deployment(VisibilityState.PRIVATE)
        self._test_cant_view_private_resource(
            resource_id=deployment_id,
            resource_name='Deployment',
            get_func_getter=lambda client: client.deployments.get
        )

    def _test_snapshots_get_and_list(self, snapshot_id):
        self._test_resource_get_and_list(
            resource_name='Snapshot',
            get_func_getter=lambda client: client.snapshots.get,
            resource_id=snapshot_id,
            list_func_getter=lambda client: client.snapshots.list
        )

    def _test_resource_get_and_list(self,
                                    resource_name,
                                    get_func_getter,
                                    resource_id,
                                    list_func_getter):
        error_msg = self.NOT_FOUND_MSG.format(resource_name, resource_id)

        # A resource uploaded with `private_resource` set to True shouldn't
        # be visible to other users
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            get_func = get_func_getter(self.client)
            list_func = list_func_getter(self.client)
            self.assertRaisesRegex(
                CloudifyClientError,
                error_msg,
                get_func,
                resource_id
            )

            self.assertEqual(len(list_func()), 0)

        # But it still should be visible to admins
        with self.use_secured_client(username='alice',
                                     password='alice_password'):
            get_func = get_func_getter(self.client)
            list_func = list_func_getter(self.client)
            get_func(resource_id)
            self.assertEqual(len(list_func()), 1)

    def _test_cant_view_private_resource(self,
                                         resource_id,
                                         resource_name,
                                         get_func_getter):
        error_msg = self.NOT_FOUND_MSG.format(resource_name, resource_id)

        # A resource uploaded with `private_resource` set to True shouldn't
        # be visible to other users (dave)
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            get_func = get_func_getter(self.client)
            self.assertRaisesRegex(
                CloudifyClientError,
                error_msg,
                get_func,
                resource_id
            )

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

from nose.plugins.attrib import attr

from manager_rest.storage import models, user_datastore
from manager_rest.test.base_test import LATEST_API_VERSION
from manager_rest.constants import OWNER_PERMISSION, VIEWER_PERMISSION

from cloudify_rest_client.exceptions import CloudifyClientError

from .test_base import SecurityTestBase


@attr(client_min_version=3, client_max_version=LATEST_API_VERSION)
class ResourcePermissionTests(SecurityTestBase):
    NOT_FOUND_MSG = '404: Requested `{0}` with ID `{1}` was not found'
    UNAUTHORIZED_MSG = "{0} does not have permissions to modify/delete {1}"

    def _upload_blueprint(self, private=False):
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
                private_resource=private
            )
        return blueprint_id

    def _create_deployment(self, private=False):
        deployment_id = 'deployment_id'
        blueprint_id = self._upload_blueprint()
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            self.client.deployments.create(blueprint_id,
                                           deployment_id,
                                           private_resource=private)
        return deployment_id

    def _upload_plugin(self, private=False):
        plugin_path = self.create_wheel('psutil', '3.3.0')

        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            plugin = self.client.plugins.upload(plugin_path,
                                                private_resource=private)
        return plugin.id

    def _upload_snapshot(self, private=False):
        snapshot_path = self.create_wheel('psutil', '3.3.0')
        snapshot_id = 'snapshot_id'

        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            self.client.snapshots.upload(snapshot_path,
                                         snapshot_id,
                                         private_resource=private)
        return snapshot_id

    def _create_snapshot(self, username, password, private=False):
        snapshot_id = 'snapshot_id'

        with self.use_secured_client(username=username, password=password):
            self.client.snapshots.create(snapshot_id=snapshot_id,
                                         include_metrics=False,
                                         include_credentials=False,
                                         private_resource=private)
        return snapshot_id

    def test_add_remove_permissions_blueprint(self):
        blueprint_id = self._upload_blueprint()
        self._test_add_remove_permissions(
            resource_class=models.Blueprint,
            resource_id=blueprint_id,
            add_permission_func_getter=lambda client:
            client.blueprints.add_permission,
            remove_permission_func_getter=lambda client:
            client.blueprints.remove_permission
        )

    def test_add_remove_permissions_plugin(self):
        plugin_id = self._upload_plugin()
        self._test_add_remove_permissions(
            resource_class=models.Plugin,
            resource_id=plugin_id,
            add_permission_func_getter=lambda client:
            client.plugins.add_permission,
            remove_permission_func_getter=lambda client:
            client.plugins.remove_permission
        )

    def test_add_remove_permissions_snapshot(self):
        snapshot_id = self._upload_snapshot()
        self._test_add_remove_permissions(
            resource_class=models.Snapshot,
            resource_id=snapshot_id,
            add_permission_func_getter=lambda client:
            client.snapshots.add_permission,
            remove_permission_func_getter=lambda client:
            client.snapshots.remove_permission
        )

    def test_add_remove_permissions_deployment(self):
        deployment_id = self._create_deployment()
        self._test_add_remove_permissions(
            resource_class=models.Deployment,
            resource_id=deployment_id,
            add_permission_func_getter=lambda client:
            client.deployments.add_permission,
            remove_permission_func_getter=lambda client:
            client.deployments.remove_permission
        )

    def test_private_blueprint(self):
        blueprint_id = self._upload_blueprint(private=True)

        self._test_resource_get_and_list(
            resource_name='Blueprint',
            get_func_getter=lambda client: client.blueprints.get,
            resource_id=blueprint_id,
            list_func_getter=lambda client: client.blueprints.list
        )

    def test_private_deployment(self):
        deployment_id = self._create_deployment(private=True)

        self._test_resource_get_and_list(
            resource_name='Deployment',
            get_func_getter=lambda client: client.deployments.get,
            resource_id=deployment_id,
            list_func_getter=lambda client: client.deployments.list
        )

    def test_private_plugin(self):
        plugin_id = self._upload_plugin(private=True)
        self._test_resource_get_and_list(
            resource_name='Plugin',
            get_func_getter=lambda client: client.plugins.get,
            resource_id=plugin_id,
            list_func_getter=lambda client: client.plugins.list
        )

    def test_private_snapshot_upload(self):
        snapshot_id = self._upload_snapshot(private=True)
        self._test_snapshots_get_and_list(snapshot_id)

    def test_private_snapshot_create(self):
        # Only admin are allowed to create snapshots, so bob should fail
        self.assertRaises(
            CloudifyClientError,
            self._create_snapshot,
            'bob',
            'bob_password'
        )
        snapshot_id = self._create_snapshot(
            'alice',
            'alice_password',
            private=True
        )
        self._test_snapshots_get_and_list(snapshot_id)

    def test_cant_view_private_blueprint(self):
        blueprint_id = self._upload_blueprint(private=True)
        self._test_cant_view_private_resource(
            resource_id=blueprint_id,
            resource_name='Blueprint',
            get_func_getter=lambda client: client.blueprints.get,
            add_permission_func_getter=lambda client:
            client.blueprints.add_permission
        )

    def test_cant_view_private_plugin(self):
        plugin_id = self._upload_plugin(private=True)
        self._test_cant_view_private_resource(
            resource_id=plugin_id,
            resource_name='Plugin',
            get_func_getter=lambda client: client.plugins.get,
            add_permission_func_getter=lambda client:
            client.plugins.add_permission
        )

    def test_cant_view_private_snapshot(self):
        snapshot_id = self._upload_snapshot(private=True)
        self._test_cant_view_private_resource(
            resource_id=snapshot_id,
            resource_name='Snapshot',
            get_func_getter=lambda client: client.snapshots.get,
            add_permission_func_getter=lambda client:
            client.snapshots.add_permission
        )

    def test_cant_view_private_deployment(self):
        deployment_id = self._create_deployment(private=True)
        self._test_cant_view_private_resource(
            resource_id=deployment_id,
            resource_name='Deployment',
            get_func_getter=lambda client: client.deployments.get,
            add_permission_func_getter=lambda client:
            client.deployments.add_permission
        )

    def test_only_owner_can_delete_blueprint(self):
        blueprint_id = self._upload_blueprint(private=True)
        self._test_only_owner_can_delete_resource(
            resource_id=blueprint_id,
            resource_class=models.Blueprint,
            delete_func_getter=lambda client: client.blueprints.delete,
            add_permission_func_getter=lambda client:
            client.blueprints.add_permission
        )

    def test_only_owner_can_delete_deployment(self):
        deployment_id = self._create_deployment(private=True)
        self._test_only_owner_can_delete_resource(
            resource_id=deployment_id,
            resource_class=models.Deployment,
            delete_func_getter=lambda client: client.deployments.delete,
            add_permission_func_getter=lambda client:
            client.deployments.add_permission
        )

    def test_only_owner_can_delete_snapshot(self):
        snapshot_id = self._upload_snapshot(private=True)
        self._test_only_owner_can_delete_resource(
            resource_id=snapshot_id,
            resource_class=models.Snapshot,
            delete_func_getter=lambda client: client.snapshots.delete,
            add_permission_func_getter=lambda client:
            client.snapshots.add_permission
        )

    def test_only_owner_can_delete_plugin(self):
        plugin_id = self._upload_plugin(private=True)
        self._test_only_owner_can_delete_resource(
            resource_id=plugin_id,
            resource_class=models.Plugin,
            delete_func_getter=lambda client: client.plugins.delete,
            add_permission_func_getter=lambda client:
            client.plugins.add_permission,
            custom_delete_message='Failed during plugin un-installation. '
                                  '(Unauthorized: 401 Unauthorized'
        )

    def _test_only_owner_can_delete_resource(self,
                                             resource_id,
                                             resource_class,
                                             delete_func_getter,
                                             add_permission_func_getter,
                                             custom_delete_message=None):
        dave = user_datastore.get_user('dave')
        resource = self.sm.get(resource_class, resource_id)
        unauthorized_error_msg = \
            custom_delete_message or self.UNAUTHORIZED_MSG.format(dave,
                                                                  resource)
        not_found_error_msg = self.NOT_FOUND_MSG.format(
            resource_class.__name__,
            resource_id
        )

        # Bob uploaded a private resource. He's the only owner and viewer
        # right now, so dave shouldn't be able to even see the resource
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            delete_func = delete_func_getter(self.client)
            self.assertRaisesRegexp(
                CloudifyClientError,
                not_found_error_msg,
                delete_func,
                resource_id
            )

        # We give dave viewer permissions on the resource
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            add_permission_func = add_permission_func_getter(self.client)
            add_permission_func(resource_id, ['dave'], VIEWER_PERMISSION)

        # Now dave can see the resource, but still can't delete it, and the
        # error message should reflect this
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            delete_func = delete_func_getter(self.client)
            with self.assertRaises(CloudifyClientError) as cm:
                delete_func(resource_id)
            self.assertIn(unauthorized_error_msg, cm.exception.message)

        # Now we give dave owner permissions on the resource
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            add_permission_func = add_permission_func_getter(self.client)
            add_permission_func(resource_id, ['dave'], OWNER_PERMISSION)

        # And finally, he's able to delete it
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            delete_func = delete_func_getter(self.client)
            delete_func(resource_id)

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
            self.assertRaisesRegexp(
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

    def _test_add_remove_permissions(self,
                                     resource_id,
                                     resource_class,
                                     add_permission_func_getter,
                                     remove_permission_func_getter):
        users_to_add = ['alice', 'dave']
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            # The resource should have an empty viewers list by default
            resource = self.sm.get(resource_class, resource_id)
            self.assertEqual(len(resource.viewers), 0)
            add_permission_func = add_permission_func_getter(self.client)
            add_permission_func(resource_id,
                                users=users_to_add,
                                permission=VIEWER_PERMISSION)
            self.sm.refresh(resource)
            self.assertEqual(len(resource.viewers), 2)
            for viewer in resource.viewers:
                self.assertIn(viewer.username, users_to_add)

            remove_permission_func = remove_permission_func_getter(self.client)
            remove_permission_func(resource_id,
                                   users=users_to_add,
                                   permission=VIEWER_PERMISSION)
            self.sm.refresh(resource)
            self.assertEqual(len(resource.viewers), 0)

    def _test_cant_view_private_resource(self,
                                         resource_id,
                                         resource_name,
                                         get_func_getter,
                                         add_permission_func_getter):
        error_msg = self.NOT_FOUND_MSG.format(resource_name, resource_id)

        # A resource uploaded with `private_resource` set to True shouldn't
        # be visible to other users (dave)
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            get_func = get_func_getter(self.client)
            self.assertRaisesRegexp(
                CloudifyClientError,
                error_msg,
                get_func,
                resource_id
            )

        # Now we add viewing permissions for dave
        with self.use_secured_client(username='bob',
                                     password='bob_password'):
            add_permission_func = add_permission_func_getter(self.client)
            add_permission_func(resource_id, ['dave'], VIEWER_PERMISSION)

        # And make sure he can indeed see the resource
        with self.use_secured_client(username='dave',
                                     password='dave_password'):
            get_func = get_func_getter(self.client)
            get_func(resource_id)

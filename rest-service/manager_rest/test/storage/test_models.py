#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

from manager_rest.storage import models, storage_manager

from mock import patch

from ..base_test import BaseStorageTestCase


def mock_filter(_, query, *args, **kwargs):
    return query


class ModelsIntegrationTests(BaseStorageTestCase):
    @patch.object(storage_manager.SQLStorageManager,
                  '_add_tenant_filter', mock_filter)
    @patch.object(storage_manager.SQLStorageManager,
                  '_add_permissions_filter', mock_filter)
    def test_create_models(self):
        self.server.db.create_all()
        self.assertEquals(len(self.sm.list(models.Blueprint)), 0)
        self.assertEquals(len(self.sm.list(models.Deployment)), 0)
        self.assertEquals(len(self.sm.list(models.DeploymentModification)), 0)
        self.assertEquals(len(self.sm.list(models.DeploymentUpdate)), 0)
        self.assertEquals(len(self.sm.list(models.DeploymentUpdateStep)), 0)
        self.assertEquals(len(self.sm.list(models.Event)), 0)
        self.assertEquals(len(self.sm.list(models.Execution)), 0)
        self.assertEquals(len(self.sm.list(models.Group)), 0)
        self.assertEquals(len(self.sm.list(models.Log)), 0)
        self.assertEquals(len(self.sm.list(models.Node)), 0)
        self.assertEquals(len(self.sm.list(models.NodeInstance)), 0)
        self.assertEquals(len(self.sm.list(models.Plugin)), 0)
        self.assertEquals(len(self.sm.list(models.ProviderContext)), 0)
        self.assertEquals(len(self.sm.list(models.Role)), 0)
        self.assertEquals(len(self.sm.list(models.Snapshot)), 0)
        self.assertEquals(len(self.sm.list(models.Tenant)), 0)
        self.assertEquals(len(self.sm.list(models.User)), 0)

    @patch.object(storage_manager.SQLStorageManager,
                  '_add_tenant_filter', mock_filter)
    @patch.object(storage_manager.SQLStorageManager,
                  '_add_permissions_filter', mock_filter)
    @patch.object(storage_manager.SQLStorageManager,
                  '_associate_users_and_tenants',
                  lambda *args: None)
    @patch.object(storage_manager.SQLStorageManager,
                  '_validate_unique_resource_id_per_tenant',
                  lambda *args: None)
    def test_model_relationship(self):
        self.server.db.create_all()
        tenant = models.Tenant(
            name='test_tenant'
        )
        self.sm.put(tenant)
        now = datetime.utcnow()
        blueprint = models.Blueprint(
            id='blueprint',
            created_at=now,
            main_file_name='mfn',
            plan={},
            updated_at=now,
            description='blabla',
            tenant_id=tenant.id,
            creator_id=tenant.id
        )
        self.sm.put(blueprint)

        deployment = models.Deployment(
            created_at=now,
            updated_at=now,
            id='dep_name',
            blueprint=blueprint,
            creator_id=tenant.id
        )
        self.sm.put(deployment)

        self.assertEquals(
            self.sm.get(models.Blueprint, blueprint.id),
            self.sm.get(models.Deployment, deployment.id).blueprint)

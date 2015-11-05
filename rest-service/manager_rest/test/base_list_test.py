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
import tempfile
import os
import shutil

from base_test import BaseServerTestCase

from wagon.wagon import Wagon


class BaseListTest(BaseServerTestCase):

    def _put_deployment_modification(self, deployment_id,
                                     modified_nodes=None,
                                     node_instances=None,
                                     nodes=None):
        resource_path = '/deployment-modifications'
        data = {'deployment_id': deployment_id,
                'modified_nodes': modified_nodes or {},
                'node_instances': node_instances or {},
                'nodes': nodes or {}}
        return self.post(resource_path, data).json

    def _mark_deployment_modification_finished(self, modification_id=None):
        resource_path = '/deployment-modifications/{0}/finish'.format(
            modification_id)
        data = {'modification_id': modification_id}
        return self.post(resource_path, data).json

    def _put_n_deployment_modifications(self, id_prefix,
                                        number_of_modifications,
                                        skip_creation=None):
        self._put_n_deployments(id_prefix,
                                number_of_modifications,
                                skip_creation=skip_creation,
                                add_modification=True)

    def _put_n_plugins(self, number_of_plugins):
        for i in range(0, number_of_plugins):
            tmpdir = tempfile.mkdtemp(prefix='test-pagination-')
            with open(os.path.join(tmpdir, 'setup.py'), 'w') as f:
                f.write('from setuptools import setup\n')
                f.write('setup(name="some-package", version={0})'.format(i))
            wagon = Wagon(tmpdir)
            plugin_path = wagon.create(archive_destination_dir=tmpdir)
            self.post_file('/plugins', plugin_path)
            shutil.rmtree(tmpdir)

    def _put_n_deployments(self, id_prefix,
                           number_of_deployments,
                           skip_creation=None,
                           add_modification=None):
        for i in range(0, number_of_deployments):
            deployment_id = "{0}{1}_{2}".format(id_prefix, str(i),
                                                'deployment')
            blueprint_id = "{0}{1}_{2}".format(id_prefix, str(i), 'blueprint')
            if not skip_creation:
                self.put_deployment(deployment_id=deployment_id,
                                    blueprint_id=blueprint_id)
            if add_modification:
                response = self._put_deployment_modification(
                    deployment_id=deployment_id)
                self._mark_deployment_modification_finished(
                    modification_id=response['id'])

    def _put_n_snapshots(self, number_of_snapshots):
        for i in range(number_of_snapshots):
            self.client.snapshots.create(snapshot_id='oh-snap{0}'.format(i),
                                         include_metrics=False,
                                         include_credentials=False)

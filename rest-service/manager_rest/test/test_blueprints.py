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

__author__ = 'dan'

import os
import tempfile

from manager_rest import archiving
from base_test import BaseServerTestCase
from cloudify_rest_client.exceptions import CloudifyClientError


class BlueprintsTestCase(BaseServerTestCase):

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_get_nonexistent_blueprint(self):
        try:
            self.client.blueprints.get('15')
        except CloudifyClientError, e:
            self.assertEqual(404, e.status_code)

    def test_server_traceback_on_error(self):
        try:
            self.client.blueprints.get('15')
        except CloudifyClientError, e:
            self.assertIsNotNone(e.server_traceback)

    def test_post_and_then_search(self):
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args(blueprint_id='hello_world')).json
        self.assertEquals('hello_world', post_blueprints_response['id'])
        get_blueprints_response = self.get('/blueprints').json
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_post_blueprint_already_exists(self):
        self.put_file(*self.put_blueprint_args())
        post_blueprints_response = self.put_file(*self.put_blueprint_args())
        self.assertTrue('already exists' in
                        post_blueprints_response.json['message'])
        self.assertEqual(409, post_blueprints_response.status_code)

    def test_put_blueprint(self):
        self._test_put_blueprint(archiving.make_targzfile, 'tar.gz')

    def test_post_without_application_file_form_data(self):
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args('blueprint_with_workflows.yaml',
                                     blueprint_id='hello_world')).json
        self.assertEquals('hello_world',
                          post_blueprints_response['id'])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args()).json
        get_blueprint_by_id_response = self.get(
            '/blueprints/{0}'.format(post_blueprints_response['id'])).json
        # setting 'source' field to be None as expected
        self.assertEquals(post_blueprints_response,
                          get_blueprint_by_id_response)

    def test_delete_blueprint(self):
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args()).json

        # testing if resources are on fileserver
        self.assertTrue(
            self.check_if_resource_on_fileserver(
                post_blueprints_response['id'], 'blueprint.yaml'))

        # deleting the blueprint that was just uploaded
        delete_blueprint_response = self.delete(
            '/blueprints/{0}'.format(post_blueprints_response['id'])).json
        self.assertEquals(post_blueprints_response['id'],
                          delete_blueprint_response['id'])

        # verifying deletion of blueprint
        resp = self.get('/blueprints/{0}'.format(post_blueprints_response[
                        'id']))
        self.assertEquals(404, resp.status_code)

        # verifying deletion of fileserver resources
        self.assertFalse(
            self.check_if_resource_on_fileserver(
                post_blueprints_response['id'], 'blueprint.yaml'))

        # trying to delete a nonexistent blueprint
        resp = self.delete('/blueprints/nonexistent-blueprint')
        self.assertEquals(404, resp.status_code)

    def test_zipped_plugin(self):
        self.put_file(*self.put_blueprint_args())
        self.check_if_resource_on_fileserver('hello_world',
                                             'plugins/stub-installer.zip')

    def test_put_blueprint_from_url(self):
        port = 54321
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)

        archive_path = self.archive_mock_blueprint()
        archive_filename = os.path.basename(archive_path)
        archive_dir = os.path.dirname(archive_path)

        from manager_rest.file_server import FileServer

        fs = FileServer(archive_dir, False, port)
        fs.start()
        try:
            response = self.put(
                resource_path,
                None,
                {'blueprint_archive_url': 'http://localhost:{0}/{'
                                          '1}'.format(port, archive_filename)})
            self.assertEqual(blueprint_id, response.json['id'])
        finally:
            fs.stop()

    def test_put_blueprint_from_unavailable_url(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            None,
            {'blueprint_archive_url': 'http://www.fake.url/does/not/exist'})
        self.assertTrue("not found - can't download blueprint archive" in
                        response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_blueprint_from_malformed_url(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            None,
            {'blueprint_archive_url': 'malformed/url_is.bad'})
        self.assertIn("is malformed - can't download blueprint archive",
                      response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_blueprint_from_url_and_data(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            'data pretending to be the actual blueprint archive data',
            {'blueprint_archive_url': 'malformed/url_is.bad'})
        self.assertIn("Can't pass both", response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_zip_blueprint(self):
        self._test_put_blueprint(archiving.make_zipfile, 'zip')

    def test_put_tar_blueprint(self):
        self._test_put_blueprint(archiving.make_tarfile, 'tar')

    def test_put_bz2_blueprint(self):
        self._test_put_blueprint(archiving.make_tarbz2file, 'tar.bz2')

    def test_put_unsupported_archive_blueprint(self):
        archive_path = tempfile.mkstemp()[1]
        with open(archive_path, 'w') as f:
            f.write('this is not a valid archive obviously')

        response = self.put_file(
            '/blueprints/unsupported_archive_bp',
            archive_path)
        self.assertIn("Blueprint archive is of an unrecognized format.",
                      response.json['message'])
        self.assertEqual(400, response.status_code)

    def _test_put_blueprint(self, archive_func, archive_type):
        blueprint_id = 'new_blueprint_id'
        put_blueprints_response = self.put_file(
            *self.put_blueprint_args(blueprint_id=blueprint_id,
                                     archive_func=archive_func)).json
        self.assertEqual(blueprint_id, put_blueprints_response['id'])

        response = self.app.get('/blueprints/{0}/archive'.format(blueprint_id))

        archive_filename = '{0}.{1}'.format(blueprint_id, archive_type)
        self.assertTrue(archive_filename in
                        response.headers['Content-Disposition'])
        self.assertTrue(archive_filename in
                        response.headers['X-Accel-Redirect'])

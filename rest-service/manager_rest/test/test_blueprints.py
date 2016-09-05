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

import os
import tempfile
import shutil

from nose.plugins.attrib import attr

from manager_rest import archiving
from manager_rest.storage.file_server import FileServer
from manager_rest.test import base_test
from cloudify_rest_client.exceptions import CloudifyClientError
from .test_utils import generate_progress_func


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class BlueprintsTestCase(base_test.BaseServerTestCase):

    def test_get_empty(self):
        result = self.client.blueprints.list()
        self.assertEquals(0, len(result))

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
        get_blueprints_response = self.client.blueprints.list()
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_post_blueprint_already_exists(self):
        self.put_file(*self.put_blueprint_args())
        post_blueprints_response = self.put_file(*self.put_blueprint_args())
        self.assertTrue('already exists' in
                        post_blueprints_response.json['message'])
        self.assertEqual(409, post_blueprints_response.status_code)

    def test_put_blueprint_archive(self):
        self._test_put_blueprint_archive(archiving.make_targzfile, 'tar.gz')

    def test_post_without_application_file_form_data(self):
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args('blueprint_with_workflows.yaml',
                                     blueprint_id='hello_world')).json
        self.assertEquals('hello_world',
                          post_blueprints_response['id'])

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_description(self):
        post_blueprints_response = self.put_file(
            *self.put_blueprint_args('blueprint.yaml',
                                     blueprint_id='blueprint')).json
        self.assertEquals('blueprint',
                          post_blueprints_response['id'])
        self.assertEquals("this is my blueprint's description",
                          post_blueprints_response['description'])

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

    def test_put_blueprint_archive_from_url(self):
        port = 53230
        blueprint_id = 'new_blueprint_id'

        archive_path = self.archive_mock_blueprint(
            archive_func=archiving.make_tarbz2file)
        archive_filename = os.path.basename(archive_path)
        archive_dir = os.path.dirname(archive_path)

        archive_url = 'http://localhost:{0}/{1}'.format(
            port, archive_filename)

        fs = FileServer(archive_dir, False, port)
        fs.start()
        try:
            self.wait_for_url(archive_url)

            blueprint_id = self.client.blueprints.publish_archive(
                archive_url,
                blueprint_id).id
            # verifying blueprint exists
            result = self.client.blueprints.get(blueprint_id)
            self.assertEqual(blueprint_id, result.id)
        finally:
            fs.stop()

    def test_put_blueprint_archive_from_unavailable_url(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            None,
            {'blueprint_archive_url': 'http://www.fake.url/does/not/exist'})
        self.assertTrue("not found - can't download blueprint archive" in
                        response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_blueprint_archive_from_malformed_url(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            None,
            {'blueprint_archive_url': 'malformed/url_is.bad'})
        self.assertIn("is malformed - can't download blueprint archive",
                      response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_blueprint_archive_from_url_and_data(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            'data pretending to be the actual blueprint archive data',
            {'blueprint_archive_url': 'malformed/url_is.bad'})
        self.assertIn("Can't pass both", response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_zip_archive(self):
        self._test_put_blueprint_archive(archiving.make_zipfile, 'zip')

    def test_put_tar_archive(self):
        self._test_put_blueprint_archive(archiving.make_tarfile, 'tar')

    def test_put_bz2_archive(self):
        self._test_put_blueprint_archive(archiving.make_tarbz2file, 'tar.bz2')

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

    def test_put_blueprint_non_existing_filename(self):
        blueprint_id = 'new_blueprint_id'
        put_blueprints_response = self.put_file(
            *self.put_blueprint_args(blueprint_id=blueprint_id,
                                     blueprint_file_name='non-existing'))

        self.assertEqual(
            put_blueprints_response.json['message'],
            'non-existing does not exist in the application directory')
        self.assertEqual(put_blueprints_response.status_code, 400)

    def test_put_blueprint_no_default_yaml(self):
        blueprint_id = 'new_blueprint_id'
        put_blueprints_response = self.put_file(
            *self.put_blueprint_args(
                blueprint_id=blueprint_id,
                blueprint_dir='mock_blueprint_no_default'))
        self.assertEqual(
            put_blueprints_response.json['message'],
            'application directory is missing blueprint.yaml and '
            'application_file_name query parameter was not passed'
        )
        self.assertEqual(put_blueprints_response.status_code, 400)

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_main_file_name(self):
        blueprint_id = 'blueprint_main_file_name'
        blueprint_file = 'blueprint_with_inputs.yaml'
        blueprint_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            blueprint_file)
        response = self.client.blueprints.upload(blueprint_path, blueprint_id)
        self.assertEqual(blueprint_file, response.main_file_name)
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_file, blueprint.main_file_name)
        blueprint = self.client.blueprints.list()[0]
        self.assertEqual(blueprint_file, blueprint.main_file_name)

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_sort_list(self):
        blueprint_file = 'blueprint_with_inputs.yaml'
        blueprint_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            blueprint_file)
        self.client.blueprints.upload(blueprint_path, '0')
        self.client.blueprints.upload(blueprint_path, '1')

        blueprints = self.client.blueprints.list(sort='created_at')
        self.assertEqual(2, len(blueprints))
        self.assertEqual('0', blueprints[0].id)
        self.assertEqual('1', blueprints[1].id)

        blueprints = self.client.blueprints.list(
            sort='created_at', is_descending=True)
        self.assertEqual(2, len(blueprints))
        self.assertEqual('1', blueprints[0].id)
        self.assertEqual('0', blueprints[1].id)

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_upload_progress(self):
        tmp_dir = '/tmp/tmp_upload_blueprint'
        blueprint_path = self._create_big_blueprint('empty_blueprint.yaml',
                                                    tmp_dir)
        progress_func = generate_progress_func(
            total_size=32917,  # Calculated by trial and error
            assert_equal=self.assertEqual,
            assert_almost_equal=self.assertAlmostEqual)

        try:
            self.client.blueprints.upload(blueprint_path, '0', progress_func)
        finally:
            self.quiet_delete_directory(tmp_dir)

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_download_progress(self):
        tmp_dir = '/tmp/tmp_upload_blueprint'
        tmp_local_path = '/tmp/blueprint.bl'

        blueprint_path = self._create_big_blueprint('empty_blueprint.yaml',
                                                    tmp_dir)
        try:
            self.client.blueprints.upload(blueprint_path, '0')
            progress_func = generate_progress_func(
                total_size=32917,  # Calculated by trial and error
                assert_equal=self.assertEqual,
                assert_almost_equal=self.assertAlmostEqual)

            self.client.blueprints.download('0', tmp_local_path, progress_func)
        finally:
            self.quiet_delete_directory(tmp_dir)
            self.quiet_delete(tmp_local_path)

    def _create_big_blueprint(self, blueprint, tmp_dir):
        """
        Create a large file, and put it in a folder with some blueprint.
        This is used in order to create a sizable blueprint archive, for
        checking upload/download
        :param blueprint: The name of the mock_blueprint file
        :param tmp_dir: The folder that will be used to store the blueprint
        and the new file
        :return: The local path of the mock blueprint
        """
        self.quiet_delete_directory(tmp_dir)
        os.mkdir(tmp_dir)

        blueprint_file = blueprint
        blueprint_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            blueprint_file)
        shutil.copy(blueprint_path, tmp_dir)
        blueprint_path = os.path.join(tmp_dir, blueprint_file)

        tmpfile_path = os.path.join(tmp_dir, 'tmp_file')
        with open(tmpfile_path, 'wb') as big_file:
            big_file.seek(32 * 1024 * 1024 - 1)
            big_file.write('\0')
        return blueprint_path

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_default_main_file_name(self):
        blueprint_id = 'blueprint_default_main_file_name'
        blueprint_file = 'blueprint.yaml'
        response = self.put_file(
            *self.put_blueprint_args(blueprint_id=blueprint_id)).json
        self.assertEquals(blueprint_file, response['main_file_name'])

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_publish_archive_blueprint_main_file_name(self):
        port = 53230
        blueprint_id = 'publish_archive_blueprint_main_file_name'
        main_file_name = 'blueprint_with_workflows.yaml'
        archive_path = self.archive_mock_blueprint()
        archive_filename = os.path.basename(archive_path)
        archive_dir = os.path.dirname(archive_path)
        fs = FileServer(archive_dir, False, port)
        fs.start()
        try:
            archive_url = 'http://localhost:{0}/{1}'.format(
                port, archive_filename)
            self.wait_for_url(archive_url)
            response = self.client.blueprints.publish_archive(archive_url,
                                                              blueprint_id,
                                                              main_file_name)
        finally:
            fs.stop()
        self.assertEqual(blueprint_id, response.id)
        self.assertEqual(main_file_name, response.main_file_name)

    def _test_put_blueprint_archive(self, archive_func, archive_type):
        blueprint_id = 'new_blueprint_id'
        put_blueprints_response = self.put_file(
            *self.put_blueprint_args(blueprint_id=blueprint_id,
                                     archive_func=archive_func)).json
        self.assertEqual(blueprint_id, put_blueprints_response['id'])

        url = self._version_url(
            '/blueprints/{0}/archive'.format(blueprint_id))
        response = self.app.get(url)

        archive_filename = '{0}.{1}'.format(blueprint_id, archive_type)
        self.assertTrue(archive_filename in
                        response.headers['Content-Disposition'])
        self.assertTrue(archive_filename in
                        response.headers['X-Accel-Redirect'])

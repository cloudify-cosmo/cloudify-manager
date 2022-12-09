#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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
import uuid
import tempfile
import shutil
from unittest import mock

import pytest

from manager_rest import archiving
from manager_rest.test import base_test
from manager_rest.storage.resource_models import Blueprint, db

from cloudify_rest_client import exceptions
from cloudify.exceptions import WorkflowFailed, InvalidBlueprintImport

from .test_utils import generate_progress_func

try:
    import bz2
except ImportError:
    bz2 = None  # type: ignore


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
            self.ok = (self.status_code == 200)
            self.text = str(self.json_data)
    return MockResponse({'error_code': 'no can do'}, 404)


class BlueprintsTestCase(base_test.BaseServerTestCase):
    LABELS = [{'key1': 'val1'}, {'key2': 'val2'}]

    def test_get_empty(self):
        result = self.client.blueprints.list()
        self.assertEqual(0, len(result))

    def test_get_nonexistent_blueprint(self):
        with self.assertRaises(exceptions.CloudifyClientError) as context:
            self.client.blueprints.get('15')
        self.assertEqual(404, context.exception.status_code)

    def test_upload_blueprint_illegal_id(self):
        # try id with whitespace
        self.assertRaisesRegex(exceptions.CloudifyClientError,
                               'contains illegal characters',
                               self.client.blueprints.upload,
                               'path',
                               'illegal id')
        # try id that starts with a number
        self.assertRaisesRegex(exceptions.CloudifyClientError,
                               'must begin with a letter',
                               self.client.blueprints.upload,
                               'path',
                               '0')

    def test_post_and_then_search(self):
        post_blueprints_response = self.put_blueprint(
            blueprint_id='hello_world')
        self.assertEqual('hello_world', post_blueprints_response['id'])
        get_blueprints_response = self.client.blueprints.list()
        self.assertEqual(1, len(get_blueprints_response))
        self.assertEqual(post_blueprints_response, get_blueprints_response[0])

    def test_post_blueprint_already_exists(self):
        self.put_blueprint()
        self.assertRaisesRegex(
            exceptions.CloudifyClientError,
            '409: blueprint with id=blueprint already exists',
            self.put_blueprint)

    def test_put_blueprint_archive(self):
        self._test_put_blueprint_archive(archiving.make_targzfile, 'tar.gz')

    def test_post_without_application_file_form_data(self):
        post_blueprints_response = self.put_blueprint(
            blueprint_file_name='blueprint_with_workflows.yaml',
            blueprint_id='hello_world')
        self.assertEqual('hello_world', post_blueprints_response['id'])

    def test_blueprint_description(self):
        post_blueprints_response = self.put_blueprint()
        self.assertEqual('blueprint',
                         post_blueprints_response['id'])
        self.assertEqual("this is my blueprint's description",
                         post_blueprints_response['description'])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.put_blueprint()
        get_blueprint_by_id_response = self.get(
            '/blueprints/{0}'.format(post_blueprints_response['id'])).json
        # setting 'source' field to be None as expected
        self.assertEqual(post_blueprints_response,
                         get_blueprint_by_id_response)

    def test_delete_blueprint(self):
        post_blueprints_response = self.put_blueprint()

        # testing if resources are uploaded
        blueprint_path = os.path.join(
            self.tmpdir,
            'blueprints',
            'default_tenant',
            post_blueprints_response['id'],
            'blueprint.yaml'
        )
        self.assertTrue(os.path.exists(blueprint_path))

        # deleting the blueprint that was just uploaded
        self.delete('/blueprints/{0}'.format(post_blueprints_response['id']))

        # verifying deletion of blueprint
        resp = self.get('/blueprints/{0}'.format(post_blueprints_response[
                        'id']))
        self.assertEqual(404, resp.status_code)

        # verifying deletion of files
        self.assertFalse(os.path.exists(blueprint_path))

        # trying to delete a nonexistent blueprint
        resp = self.delete('/blueprints/nonexistent-blueprint')
        self.assertEqual(404, resp.status_code)

    def test_put_blueprint_archive_from_url_and_data(self):
        blueprint_id = 'new_blueprint_id'
        resource_path = '/blueprints/{0}'.format(blueprint_id)
        response = self.put(
            resource_path,
            'data pretending to be the actual blueprint archive data',
            {'blueprint_archive_url': 'malformed/url_is.bad'})
        self.assertIn("Can pass blueprint as only one of",
                      response.json['message'])
        self.assertEqual(400, response.status_code)

    def test_put_zip_archive(self):
        self._test_put_blueprint_archive(archiving.make_zipfile, 'zip')

    def test_put_tar_archive(self):
        self._test_put_blueprint_archive(archiving.make_tarfile, 'tar')

    @pytest.mark.skipif(bz2 is None, reason='bz2 module not available')
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
        with self.assertRaisesRegex(WorkflowFailed, 'non-existing'):
            self.put_blueprint(
                blueprint_id=blueprint_id, blueprint_file_name='non-existing')

    def test_put_blueprint_no_default_yaml(self):
        blueprint_id = 'new_blueprint_id'
        with self.assertRaisesRegex(WorkflowFailed, 'blueprint.yaml'):
            self.put_blueprint(blueprint_id=blueprint_id,
                               blueprint_dir='mock_blueprint_no_default')

    def test_blueprint_main_file_name(self):
        blueprint_id = 'blueprint_main_file_name'
        blueprint_file = 'blueprint_with_inputs.yaml'
        response = self.put_blueprint(
            'mock_blueprint',
            'blueprint_with_inputs.yaml',
            'blueprint_main_file_name')
        self.assertEqual(blueprint_file, response['main_file_name'])
        blueprint = self.client.blueprints.get(blueprint_id)
        self.assertEqual(blueprint_file, blueprint.main_file_name)
        blueprint = self.client.blueprints.list()[0]
        self.assertEqual(blueprint_file, blueprint.main_file_name)

    def test_sort_list(self):
        blueprint_file = 'blueprint_with_inputs.yaml'
        blueprint_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            blueprint_file)
        self.client.blueprints.upload(blueprint_path, 'b0', async_upload=True)
        self.client.blueprints.upload(blueprint_path, 'b1', async_upload=True)

        blueprints = self.client.blueprints.list(sort='created_at')
        self.assertEqual(2, len(blueprints))
        self.assertEqual('b0', blueprints[0].id)
        self.assertEqual('b1', blueprints[1].id)

        blueprints = self.client.blueprints.list(
            sort='created_at', is_descending=True)
        self.assertEqual(2, len(blueprints))
        self.assertEqual('b1', blueprints[0].id)
        self.assertEqual('b0', blueprints[1].id)

    def test_upload_skip_execution(self):
        bp_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            'blueprint_with_inputs.yaml',
        )
        self.client.blueprints.upload(bp_path, 'b0', skip_execution=True)

        assert not self.client.executions.list(workflow_id='upload_blueprint')

        outfile = os.path.join(self.tmpdir, 'skip-execution-blueprint')
        self.addCleanup(self.quiet_delete, outfile)
        self.client.blueprints.download('b0', output_file=outfile)
        assert os.path.exists(outfile)

    def test_blueprint_download_progress(self):
        tmp_dir = '/tmp/tmp_upload_blueprint'
        tmp_local_path = '/tmp/blueprint.bl'

        blueprint_path = self._create_big_blueprint('empty_blueprint.yaml',
                                                    tmp_dir)

        size = self.client.blueprints.calc_size(blueprint_path)

        try:
            self.client.blueprints.upload(blueprint_path, 'b',
                                          async_upload=True)
            progress_func = generate_progress_func(total_size=size)

            self.client.blueprints.download('b', tmp_local_path, progress_func)
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
            big_file.write(b'\0')
        return blueprint_path

    def test_blueprint_default_main_file_name(self):
        blueprint_id = 'blueprint_default_main_file_name'
        blueprint_file = 'blueprint.yaml'
        response = self.put_blueprint(
            'mock_blueprint', blueprint_file, blueprint_id)
        self.assertEqual(blueprint_file, response['main_file_name'])

    def _test_put_blueprint_archive(self, archive_func, archive_type):
        blueprint_id = 'b{0}'.format(str(uuid.uuid4()))
        self.put_file(
            *self.put_blueprint_args(blueprint_id=blueprint_id,
                                     archive_func=archive_func)).json

        url = self._version_url(
            '/blueprints/{0}/archive'.format(blueprint_id))
        response = self.app.get(url)

        archive_filename = '{0}.{1}'.format(blueprint_id, archive_type)
        self.assertTrue(archive_filename in
                        response.headers['Content-Disposition'])
        self.assertTrue(archive_filename in
                        response.headers['X-Accel-Redirect'])

    def test_delete_used_blueprints_via_import(self):
        """
        Test deletion protection of a blueprint which is used in another
        blueprint.
        """
        second_blueprint_id = 'imported_blueprint'
        self.put_blueprint('mock_blueprint',
                           'blueprint.yaml', second_blueprint_id)

        first_blueprint_id = 'first_imported_blueprint'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_blueprint_import.yaml',
                           first_blueprint_id)

        app_blueprint_id = 'app'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_2_layer_blueprint_import.yaml',
                           app_blueprint_id)

        self.assertRaises(exceptions.BlueprintInUseError,
                          self.client.blueprints.delete,
                          first_blueprint_id)

        self.assertRaises(exceptions.BlueprintInUseError,
                          self.client.blueprints.delete,
                          second_blueprint_id)

        self.client.blueprints.delete(app_blueprint_id)
        self.client.blueprints.delete(first_blueprint_id)
        self.client.blueprints.delete(second_blueprint_id)

    def test_force_delete_used_blueprints_via_import(self):
        """
        Test force deletion protection of a blueprint which is used in another
        blueprint.
        """
        first_blueprint_id = 'imported_blueprint'
        self.put_blueprint('mock_blueprint',
                           'blueprint.yaml', first_blueprint_id)

        app_blueprint_id = 'first_imported_blueprint'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_blueprint_import.yaml',
                           app_blueprint_id)

        self.assertRaises(exceptions.BlueprintInUseError,
                          self.client.blueprints.delete,
                          first_blueprint_id)

        self.client.blueprints.delete(first_blueprint_id, True)

    def test_not_listing_hidden_blueprints(self):
        b0_id = 'b0'
        b1_id = 'b1'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           b0_id)
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           b1_id)

        blueprint_b1 = self.sm.get(Blueprint, b1_id)
        blueprint_b1.is_hidden = True
        self.sm.update(blueprint_b1)

        blueprints = self.client.blueprints.list()
        self.assertEqual(1, len(blueprints))
        self.assertEqual(b0_id, blueprints[0].id)

    def test_blueprint_validate_invalid_id(self):
        blueprint_id = 'invalid blueprint id'
        blueprint_file = 'blueprint.yaml'
        blueprint_path = os.path.join(
            self.get_blueprint_path('mock_blueprint'),
            blueprint_file)
        with self.assertRaises(exceptions.CloudifyClientError) as context:
            self.client.blueprints.validate(blueprint_path, blueprint_id)
        self.assertEqual(400, context.exception.status_code)
        self.assertIn(
            "The `blueprint_id` argument contains illegal characters.",
            str(context.exception))

    def test_blueprint_update_state(self):
        blueprint_id = 'blue_state'
        new_state = 'failed_uploading'
        new_error = 'Error: some message'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        blueprint = self.sm.get(Blueprint, blueprint_id, include=[
            'plan', 'created_at', 'updated_at', 'visibility', 'state',
            'error'])
        db.session.expunge(blueprint)
        self.client.blueprints.update(blueprint_id, {'state': new_state,
                                                     'error': new_error})
        updated_blueprint = self.sm.get(Blueprint, blueprint_id, include=[
            'plan', 'created_at', 'updated_at', 'visibility', 'state',
            'error'])

        assert blueprint.created_at == updated_blueprint.created_at
        assert blueprint.updated_at < updated_blueprint.updated_at
        assert blueprint.plan == updated_blueprint.plan
        assert blueprint.visibility == updated_blueprint.visibility
        assert blueprint.state != updated_blueprint.state
        assert blueprint.error != updated_blueprint.error
        assert updated_blueprint.state == new_state
        assert updated_blueprint.error == new_error

    def test_blueprint_update_invalid_state(self):
        blueprint_id = 'blue_invalid_state'
        new_state = 'nonsuch_state'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        self.assertRaisesRegex(
            exceptions.CloudifyClientError,
            'Invalid state: `{0}`'.format(new_state),
            self.client.blueprints.update,
            blueprint_id,
            {'state': new_state}
        )

    def test_blueprint_update_invalid_param(self):
        blueprint_id = 'blue_invalid_param'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        self.assertRaisesRegex(
            exceptions.CloudifyClientError,
            'Unknown parameters: abc',
            self.client.blueprints.update,
            blueprint_id,
            {'abc': 123}
        )

    def test_blueprint_update_invalid_param_type(self):
        blueprint_id = 'blue_invalid_param_type'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        self.assertRaisesRegex(
            exceptions.CloudifyClientError,
            'visibility parameter is expected to be of type {}'.format(
                str.__name__),
            self.client.blueprints.update,
            blueprint_id,
            {'visibility': 123}
        )
        self.assertRaisesRegex(
            exceptions.CloudifyClientError,
            'plan parameter is expected to be of type dict',
            self.client.blueprints.update,
            blueprint_id,
            {'plan': 'abcd'}
        )

    @mock.patch('cloudify_rest_client.manager.ManagerClient.get_managers',
                return_value=[{'distribution': 'centos',
                               'distro_release': 'Core'}])
    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_blueprint_upload_autoupload_plugins_network_failure(
            self, mock_get, mock_get_managers):
        blueprint_id = 'bp_with_plugin_import_no_github'
        self.assertRaisesRegex(
            InvalidBlueprintImport,
            'Couldn\'t download plugin cloudify-diamond-plugin',
            self.put_blueprint,
            'mock_blueprint',
            'blueprint_with_plugin_import.yaml',
            blueprint_id)

    def test_list_blueprints_with_filter_id(self):
        self.put_blueprint_with_labels(self.LABELS, blueprint_id='bp1')
        bp2 = self.put_blueprint_with_labels(self.LABELS_2, blueprint_id='bp2')
        self.create_filter(self.client.blueprints_filters,
                           self.FILTER_ID, self.FILTER_RULES)
        blueprints = self.client.blueprints.list(
            filter_id=self.FILTER_ID)
        self.assertEqual(len(blueprints), 1)
        self.assertEqual(blueprints[0], bp2)
        self.assert_metadata_filtered(blueprints, 1)

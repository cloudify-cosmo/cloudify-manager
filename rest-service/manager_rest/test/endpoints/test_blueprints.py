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

from manager_rest import archiving
from manager_rest.test import base_test
from manager_rest.test.attribute import attr
from manager_rest.storage.resource_models import Blueprint
from manager_rest.manager_exceptions import DslParseException

from cloudify._compat import text_type
from cloudify_rest_client import exceptions

from .test_utils import generate_progress_func


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
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
        self.assertRaisesRegexp(
            exceptions.CloudifyClientError,
            '409: blueprint with id=blueprint already exists',
            callable_obj=self.put_blueprint)

    def test_put_blueprint_archive(self):
        self._test_put_blueprint_archive(archiving.make_targzfile, 'tar.gz')

    def test_post_without_application_file_form_data(self):
        post_blueprints_response = self.put_blueprint(
            blueprint_file_name='blueprint_with_workflows.yaml',
            blueprint_id='hello_world')
        self.assertEqual('hello_world', post_blueprints_response['id'])

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
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

        # testing if resources are on fileserver
        self.assertTrue(
            self.check_if_resource_on_fileserver(
                post_blueprints_response['id'], 'blueprint.yaml'))

        # deleting the blueprint that was just uploaded
        self.delete('/blueprints/{0}'.format(post_blueprints_response['id']))

        # verifying deletion of blueprint
        resp = self.get('/blueprints/{0}'.format(post_blueprints_response[
                        'id']))
        self.assertEqual(404, resp.status_code)

        # verifying deletion of fileserver resources
        self.assertFalse(
            self.check_if_resource_on_fileserver(
                post_blueprints_response['id'], 'blueprint.yaml'))

        # trying to delete a nonexistent blueprint
        resp = self.delete('/blueprints/nonexistent-blueprint')
        self.assertEqual(404, resp.status_code)

    def test_zipped_plugin(self):
        self.put_file(*self.put_blueprint_args())
        self.check_if_resource_on_fileserver('hello_world',
                                             'plugins/stub-installer.zip')

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
        self.assertRaisesRegexp(
            DslParseException,
            'No such file or directory: .*non-existing',
            self.put_blueprint,
            blueprint_id=blueprint_id,
            blueprint_file_name='non-existing')

    def test_put_blueprint_no_default_yaml(self):
        blueprint_id = 'new_blueprint_id'
        self.assertRaisesRegexp(
            DslParseException,
            'No such file or directory: .*blueprint.yaml',
            self.put_blueprint,
            blueprint_id=blueprint_id,
            blueprint_dir='mock_blueprint_no_default')

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_upload_progress(self):
        tmp_dir = '/tmp/tmp_upload_blueprint'
        blueprint_path = self._create_big_blueprint('empty_blueprint.yaml',
                                                    tmp_dir)

        size = self.client.blueprints.calc_size(blueprint_path)

        progress_func = generate_progress_func(total_size=size)

        try:
            self.client.blueprints.upload(blueprint_path, 'b',
                                          progress_callback=progress_func,
                                          async_upload=True)
        finally:
            self.quiet_delete_directory(tmp_dir)

    @attr(client_min_version=3,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=2,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
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

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_update_invalid_state(self):
        blueprint_id = 'blue_invalid_state'
        new_state = 'nonsuch_state'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        self.assertRaisesRegexp(
            exceptions.CloudifyClientError,
            'Invalid state: `{0}`'.format(new_state),
            self.client.blueprints.update,
            blueprint_id,
            {'state': new_state}
        )

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_update_invalid_param(self):
        blueprint_id = 'blue_invalid_param'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        self.assertRaisesRegexp(
            exceptions.CloudifyClientError,
            'Unknown parameters: abc',
            self.client.blueprints.update,
            blueprint_id,
            {'abc': 123}
        )

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_update_invalid_param_type(self):
        blueprint_id = 'blue_invalid_param_type'
        self.put_blueprint('mock_blueprint',
                           'blueprint_with_inputs.yaml',
                           blueprint_id)
        self.assertRaisesRegexp(
            exceptions.CloudifyClientError,
            'visibility parameter is expected to be of type {}'.format(
                text_type.__name__),
            self.client.blueprints.update,
            blueprint_id,
            {'visibility': 123}
        )
        self.assertRaisesRegexp(
            exceptions.CloudifyClientError,
            'plan parameter is expected to be of type dict',
            self.client.blueprints.update,
            blueprint_id,
            {'plan': 'abcd'}
        )

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_list_blueprints_with_filter_rules(self):
        for i in range(1, 3):
            bp_file_name = 'blueprint_with_labels_{0}.yaml'.format(i)
            bp_id = 'blueprint_{0}'.format(i)
            self.put_blueprint(blueprint_id=bp_id,
                               blueprint_file_name=bp_file_name)
        all_blueprints = self.client.blueprints.list(
            filter_rules={'_filter_rules': ['bp_key1=bp_key1_val1']})
        second_blueprint = self.client.blueprints.list(
            filter_rules={'_filter_rules': ['bp_key2=bp_2_val1',
                                            'bp_key1 is not null']})
        self.assertEqual(len(all_blueprints), 2)
        self.assert_metadata_filtered(all_blueprints, 0)
        self.assertEqual(len(second_blueprint), 1)
        self.assert_metadata_filtered(second_blueprint, 1)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_blueprint_labels(self):
        new_labels = [{'key2': 'val2'}, {'key3': 'val3'}]
        blueprint = self.put_blueprint_with_labels(self.LABELS)
        updated_bp = self.client.blueprints.update(blueprint['id'],
                                                   {'labels': new_labels})
        self.assert_resource_labels(updated_bp['labels'], new_labels)

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_update_empty_blueprint_labels(self):
        blueprint = self.put_blueprint_with_labels(self.LABELS)
        updated_bp = self.client.blueprints.update(blueprint['id'],
                                                   {'labels': []})
        self.assert_resource_labels(updated_bp['labels'], [])

    @attr(client_min_version=3.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_blueprint_update_failure_with_duplicate_labels(self):
        update_dict = {'labels': [{'key3': 'val3'}, {'key3': 'val3'}]}
        blueprint = self.put_blueprint_with_labels(self.LABELS)
        error_msg = '400: .*You cannot define the same label twice'
        self.assertRaisesRegex(exceptions.CloudifyClientError,
                               error_msg,
                               self.client.blueprints.update,
                               blueprint_id=blueprint['id'],
                               update_dict=update_dict)

    def test_blueprint_update_new_labels(self):
        new_labels = [{'key': 'val1'}]
        blueprint = self.put_blueprint()
        updated_bp = self.client.blueprints.update(blueprint['id'],
                                                   {'labels': new_labels})
        self.assert_resource_labels(updated_bp['labels'], new_labels)

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
import shutil
import tempfile
import contextlib

from urllib2 import urlopen, URLError

from flask import request

from manager_rest import manager_exceptions
from manager_rest import chunked
from manager_rest import config


class UploadedDataManager(object):

    def receive_uploaded_data(self, data_id):
        file_server_root = config.instance().file_server_root
        archive_target_path = tempfile.mktemp(dir=file_server_root)
        try:
            self._save_file_locally(archive_target_path)
            doc, dest_file_name = self._prepare_and_process_doc(
                data_id,
                file_server_root,
                archive_target_path)
            self._move_archive_to_uploaded_dir(doc.id,
                                               file_server_root,
                                               archive_target_path,
                                               dest_file_name=dest_file_name)

            return doc, 201
        finally:
            if os.path.exists(archive_target_path):
                os.remove(archive_target_path)

    def _save_file_locally(self, archive_target_path):
        url_key = self._get_data_url_key()
        if url_key in request.args:
            if request.data or 'Transfer-Encoding' in request.headers:
                raise manager_exceptions.BadParametersError(
                    "Can't pass both a {0} URL via query parameters "
                    "and {0} data via the request body at the same time"
                    .format(self._get_kind()))
            data_url = request.args[url_key]
            try:
                with contextlib.closing(urlopen(data_url)) as urlf:
                    with open(archive_target_path, 'w') as f:
                        f.write(urlf.read())
            except URLError:
                raise manager_exceptions.ParamUrlNotFoundError(
                    "URL {0} not found - can't download {1} archive"
                    .format(data_url, self._get_kind()))
            except ValueError:
                raise manager_exceptions.BadParametersError(
                    "URL {0} is malformed - can't download {1} archive"
                    .format(data_url, self._get_kind()))

        elif 'Transfer-Encoding' in request.headers:
            with open(archive_target_path, 'w') as f:
                for buffered_chunked in chunked.decode(request.input_stream):
                    f.write(buffered_chunked)
        else:
            if not request.data:
                raise manager_exceptions.BadParametersError(
                    'Missing {0} archive in request body or '
                    '"{1}" in query parameters'.format(self._get_kind(),
                                                       url_key))
            uploaded_file_data = request.data
            with open(archive_target_path, 'w') as f:
                f.write(uploaded_file_data)

    def _move_archive_to_uploaded_dir(self,
                                      data_id,
                                      root_path,
                                      archive_path,
                                      dest_file_name=None):
        if not os.path.exists(archive_path):
            raise RuntimeError("Archive [{0}] doesn't exist - Cannot move "
                               "archive to uploaded {1}s "
                               "directory".format(archive_path,
                                                  self._get_kind()))
        uploaded_dir = os.path.join(
            root_path,
            self._get_target_dir_path(),
            data_id)
        if not os.path.isdir(uploaded_dir):
            os.makedirs(uploaded_dir)
        archive_type = self._get_archive_type(archive_path)
        if not dest_file_name:
            dest_file_name = '{0}.{1}'.format(data_id, archive_type)
        shutil.move(archive_path,
                    os.path.join(uploaded_dir, dest_file_name))

    def _get_kind(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_data_url_key(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_target_dir_path(self):
        raise NotImplementedError('Subclass responsibility')

    def _get_archive_type(self, archive_path):
        raise NotImplementedError('Subclass responsibility')

    def _prepare_and_process_doc(self, data_id, file_server_root,
                                 archive_target_path):
        raise NotImplementedError('Subclass responsibility')

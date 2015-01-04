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
import tarfile
import zipfile


def make_tarfile(output_filename, source_dir):
    _make_tarfile(output_filename, source_dir)


def make_targzfile(output_filename, source_dir):
    _make_tarfile(output_filename, source_dir, 'w:gz')


def make_tarbz2file(output_filename, source_dir):
    _make_tarfile(output_filename, source_dir, 'w:bz2')


def make_zipfile(output_filename, source_dir):
    with zipfile.ZipFile(output_filename, 'w') as zip:
        _zipdir(source_dir, zip)


def _make_tarfile(output_filename, source_dir, write_type='w'):
    with tarfile.open(output_filename, write_type) as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def _zipdir(path, zip):
    # archives the directory at 'path' *including* the directory itself,
    # with each file receiving the arcname relative to the 'path' directory.

    orig_root_abspath = os.path.dirname(os.path.abspath(path))

    for root, dirs, files in os.walk(path):
        root_abspath = os.path.abspath(root)
        arcname = root_abspath[len(orig_root_abspath) + 1:]
        zip.write(root, arcname=arcname)

        for file in files:
            file_abspath = os.path.abspath(os.path.join(root, file))
            arcname = file_abspath[len(orig_root_abspath) + 1:]
            zip.write(os.path.join(root, file), arcname=arcname)

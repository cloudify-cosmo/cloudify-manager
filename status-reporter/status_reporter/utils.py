#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import yaml


def read_from_yaml_file(file_path):
    with open(file_path, 'r') as f:
        file_content = f.read()
        try:
            return yaml.safe_load(file_content)
        except yaml.YAMLError as e:
            raise yaml.YAMLError('Failed to load yaml file {0}, due to '
                                 '{1}'.format(file_path, str(e)))


def _write_to_file(content, file_path):
    with open(file_path, 'w') as f:
        f.write(content)


def update_yaml_file(yaml_path, updated_content):
    if not isinstance(updated_content, dict):
        raise ValueError('Expected input of type dict, got {0} '
                         'instead'.format(type(updated_content)))
    if os.path.exists(yaml_path) and os.path.isfile(yaml_path):
        yaml_content = read_from_yaml_file(yaml_path)
    else:
        yaml_content = {}

    yaml_content.update(**updated_content)
    updated_file = yaml.safe_dump(yaml_content,
                                  default_flow_style=False)
    _write_to_file(updated_file, yaml_path)

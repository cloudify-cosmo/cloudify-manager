#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import yaml
import collections
from os.path import isfile
from yaml.parser import ParserError

from .exceptions import InputError
from .constants import USER_CONFIG_PATH, DEFAULT_CONFIG_PATH


def dict_merge(dct, merge_dct):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    Taken from: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.iteritems():
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


class Config(dict):
    def __init__(self, *args, **kwargs):
        super(Config, self).__init__(*args, **kwargs)

    def _load_defaults_config(self):
        default_config = self._load_yaml(DEFAULT_CONFIG_PATH)
        self.update(default_config)

    def _load_user_config(self):
        # Allow `config.yaml` not to exist - this is normal for teardown
        if isfile(USER_CONFIG_PATH):
            # Override any default values with values from config.yaml
            user_config = self._load_yaml(USER_CONFIG_PATH)
            dict_merge(self, user_config)

    @staticmethod
    def _load_yaml(path_to_yaml):
        with open(path_to_yaml, 'r') as f:
            try:
                return yaml.load(f)
            except ParserError as e:
                raise InputError(
                    'User config file {0} is not a properly formatted '
                    'YAML file:\n{1}'.format(path_to_yaml, e)
                )

    def load_config(self):
        self._load_defaults_config()
        self._load_user_config()

    def add_temp_path_to_clean(self, new_path_to_remove):
        paths_to_remove = self.setdefault('temp_paths_to_remove', [])
        paths_to_remove.append(new_path_to_remove)


config = Config()

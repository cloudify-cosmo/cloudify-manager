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

import importlib

from flask import g

# storage_manager_module_name = 'file_storage_manager'
storage_manager_module_name = 'manager_rest.es_storage_manager'

_instance = None


def _create_instance():
    module = importlib.import_module(storage_manager_module_name)
    return module.create()


def reset():
    global _instance
    _instance = _create_instance()


def instance():
    global _instance
    if _instance is None:
        _instance = _create_instance()
    return _instance


def teardown_storage_manager(exception):
    # print "tearing down storage manager!"
    pass


def get_storage_manager():
    return g.storage_manager

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
from flask import current_app

# storage_manager_module_name = 'file_storage_manager'
storage_manager_module_name = 'manager_rest.storage.sql_storage_manager'

_instance = None


def _create_instance():
    module = importlib.import_module(storage_manager_module_name)
    return module.create()


def reset():
    global _instance
    _instance = _create_instance()


def _get_instance():
    global _instance
    if _instance is None:
        _instance = _create_instance()
    return _instance


def teardown_storage_manager(exception):
    # print "tearing down storage manager!"
    pass


# What we need to access this manager in Flask
def get_storage_manager():
    """
    Get the current app's storage manager, create if necessary
    """
    manager = current_app.config.get('storage_manager')
    if not manager:
        current_app.config['storage_manager'] = _get_instance()
        manager = current_app.config.get('storage_manager')
    return manager


class ListResult(object):
    """
    a ListResult contains results about the requested items.
    """
    def __init__(self, items, metadata):
        self.items = items
        self.metadata = metadata

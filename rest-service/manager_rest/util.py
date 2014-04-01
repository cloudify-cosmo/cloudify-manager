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

from os import path
import shutil


__author__ = 'dank'


def copy_resources(file_server_root):
    cloudify_resources = path.abspath(__file__)
    for i in range(3):
        cloudify_resources = path.dirname(cloudify_resources)
    cloudify_resources = path.join(cloudify_resources,
                                   'resources',
                                   'rest-service',
                                   'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root,
                                                  'cloudify'))


def maybe_register_teardown(app, f):
    """
    A way to add a cleanup hook on a given appcontext - but only do it once
    """
    if f not in app.teardown_appcontext_funcs:
        app.teardown_appcontext_funcs.append(f)

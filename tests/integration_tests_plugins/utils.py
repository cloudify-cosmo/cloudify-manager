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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import json
import os
from contextlib import contextmanager

import fasteners


@contextmanager
def update_storage(ctx, plugin_name=None):
    """
    A context manager for updating plugin state.

    :param plugin_name: Pass directly if running from a WF context
    :param ctx: task invocation context
    """

    deployment_id = ctx.deployment.id or 'system'
    plugin_name = plugin_name or ctx.plugin.name
    if not plugin_name:
        # hack for tasks that are executed locally.
        if ctx.task_name.startswith('cloudify_agent'):
            plugin_name = 'agent'

    plugins_storage_dir = '/tmp/integration-plugin-storage'
    if not os.path.exists(plugins_storage_dir):
        os.makedirs(plugins_storage_dir)
    storage_file_path = os.path.join(
        plugins_storage_dir,
        '{0}.json'.format(plugin_name)
    )

    with storage_file_lock(storage_file_path):
        # create storage file if it doesn't exist
        if not os.path.exists(storage_file_path):
            with open(storage_file_path, 'w') as f:
                json.dump({}, f)
            os.chmod(storage_file_path, 0o666)
        with open(storage_file_path, 'r') as f:
            try:
                data = json.load(f)
            except ValueError:
                data = {}
        yield data.setdefault(deployment_id, {})
        with open(storage_file_path, 'w') as f:
            json.dump(data, f, indent=2)
            f.write(os.linesep)


@contextmanager
def storage_file_lock(storage_file_path):
    with fasteners.InterProcessLock('{0}.lock'.format(storage_file_path)):
        yield

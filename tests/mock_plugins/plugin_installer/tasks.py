########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import shutil
import os
import mock_plugins

from os.path import join
from os.path import dirname
from os.path import basename
from cloudify.decorators import operation
from shutil import ignore_patterns


@operation
def install(ctx, plugins, **kwargs):

    for plugin in plugins:
        ctx.logger.info('Installing plugin {0}'.format(plugin['name']))
        install_plugin(plugin)


def install_plugin(plugin):
    plugin_dir = os.path.join(
        dirname(mock_plugins.__file__),
        plugin['source']
    )
    dst = join(os.environ['ENV_DIR'], basename(plugin_dir))
    if not os.path.exists(dst):
        shutil.copytree(src=plugin_dir,
                        dst=dst,
                        ignore=ignore_patterns('*.pyc'))

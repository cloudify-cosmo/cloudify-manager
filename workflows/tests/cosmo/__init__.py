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

__author__ = 'idanmo'

import fnmatch
import os


def build_includes(workdir, app):
    includes = []
    for root, dirnames, filenames in os.walk(os.path.join(workdir, app)):
        for filename in fnmatch.filter(filenames, 'tasks.py'):
            includes.append(os.path.join(root, filename))

    # remove .py suffix from include
    includes = map(lambda include: include[:-3], includes)

    # remove path prefix to start with cosmo
    includes = map(lambda include: include.replace(workdir, ''), includes)

    # replace slashes with dots in include path
    includes = map(lambda include: include.replace('/', '.'), includes)

    # remove the dot at the start
    includes = map(lambda include: include[1:], includes)

    return includes

includes = build_includes(os.getcwd(), 'cosmo')

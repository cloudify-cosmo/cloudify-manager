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

from cloudify.decorators import operation


NON_EXISTING_OPERATIONS = ['testmockoperations.non_existent']


@operation
def install(ctx, plugin, **kwargs):
    pass


@operation
def verify_plugin(ctx, worker_id, plugin_name, operation, throw_on_failure,
                  **kwargs):
    full_operation_name = "{0}.{1}".format(plugin_name, operation)
    is_non_existing = full_operation_name in NON_EXISTING_OPERATIONS
    if throw_on_failure and is_non_existing:
        raise RuntimeError("")
    return not is_non_existing


@operation
def get_arguments(plugin_name, operation, **kwargs):
    pass

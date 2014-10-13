########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

from contextlib import contextmanager

from cloudify.decorators import operation


class UpdatedNodeInstance(Exception):
    pass


@operation
def get_state(**kwargs):
    return True


@operation
def nop_and_assert_no_runtime_update(ctx, **kwargs):
    with mocked_update_node_instance(ctx):
        # nothing should happen here
        ctx.instance.update()


@operation
def read_runtime_properties_and_assert_no_runtime_update(ctx, **kwargs):
    props = ctx.instance.runtime_properties
    ctx.logger.info('got these props: {0}'.format(props))
    with mocked_update_node_instance(ctx):
        # nothing should happen here
        ctx.instance.update()


@operation
def change_runtime_properties_and_assert_runtime_update(ctx, **kwargs):
    props = ctx.instance.runtime_properties
    props['prop'] = 'value'
    ctx.logger.info('changed these props: {0}'.format(props))
    with mocked_update_node_instance(ctx):
        try:
            # should actually try and update
            ctx.instance.update()
        except UpdatedNodeInstance:
            return
    raise RuntimeError('update node instance should have been called')


@contextmanager
def mocked_update_node_instance(ctx):

    def mock_update_node_instance(_):
        raise UpdatedNodeInstance()

    original_update_node_instance = ctx._endpoint.update_node_instance
    ctx._endpoint.update_node_instance = mock_update_node_instance
    try:
        yield
    finally:
        ctx._endpoint.update_node_instance = original_update_node_instance

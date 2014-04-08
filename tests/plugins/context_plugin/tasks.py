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


class UpdatedNodeState(Exception):
    pass


@operation
def get_state(**kwargs):
    return True


@operation
def nop_and_assert_no_runtime_update(ctx, **kwargs):
    with mocked_update_node_state():
        # nothing should happen here
        ctx.update()


@operation
def read_runtime_properties_and_assert_no_runtime_update(ctx, **kwargs):
    props = ctx.runtime_properties
    ctx.logger.info('got these props: {0}'.format(props))
    with mocked_update_node_state():
        # nothing should happen here
        ctx.update()


@operation
def change_runtime_properties_and_assert_runtime_update(ctx, **kwargs):
    props = ctx.runtime_properties
    props['prop'] = 'value'
    ctx.logger.info('changed these props: {0}'.format(props))
    with mocked_update_node_state():
        try:
            # should actually try and update
            ctx.update()
        except UpdatedNodeState:
            return
    raise RuntimeError('update node state should have been called')


@contextmanager
def mocked_update_node_state():

    def mock_update_node_state(_):
        raise UpdatedNodeState()

    from cloudify import context
    original_update_node_state = context.update_node_state
    context.update_node_state = mock_update_node_state
    try:
        yield
    finally:
        context.update_node_state = original_update_node_state

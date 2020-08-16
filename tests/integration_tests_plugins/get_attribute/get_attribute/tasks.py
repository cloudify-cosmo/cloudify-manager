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

from cloudify.decorators import operation
from cloudify import constants
from cloudify import ctx


@operation
def setup(source, target, **_):
    ctx.source.instance.runtime_properties.update(source)
    ctx.target.instance.runtime_properties.update(target)


def assertEqual(left, right):
    if left != right:
        raise AssertionError('{0} != {1}'.format(left, right))


@operation
def assertion(a=None, b=None, c=None, d=None, **_):
    if ctx.type == constants.NODE_INSTANCE:
        assertEqual(a, 'a_value')
        assertEqual(b, 'b_value')
        assertEqual(c, None)
        assertEqual(d, None)
        invocations = ctx.instance.runtime_properties.get('invocations', [])
        invocations.append(ctx.type)
        ctx.instance.runtime_properties['invocations'] = invocations
    else:
        assertEqual(a, None)
        assertEqual(b, None)
        assertEqual(c, 'c_value')
        assertEqual(d, 'd_value')
        invocations = ctx.source.instance.runtime_properties.get(
            'invocations', [])
        invocations.append(ctx.type)
        ctx.source.instance.runtime_properties['invocations'] = invocations

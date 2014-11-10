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


from nose.tools import eq_ as assertEqual

from cloudify.decorators import operation
from cloudify import context
from cloudify import ctx

from testenv.utils import update_storage


@operation
def setup(source, target, **_):
    ctx.source.instance.runtime_properties.update(source)
    ctx.target.instance.runtime_properties.update(target)


@operation
def assertion(a=None, b=None, c=None, d=None, **_):
    if ctx.type == context.NODE_INSTANCE:
        assertEqual(a, 'a_value')
        assertEqual(b, 'b_value')
        assertEqual(c, None)
        assertEqual(d, None)
    else:
        assertEqual(a, None)
        assertEqual(b, None)
        assertEqual(c, 'c_value')
        assertEqual(d, 'd_value')
    with update_storage(ctx) as data:
        invocations = data.get('invocations', [])
        data['invocations'] = invocations
        invocations.append(ctx.type)

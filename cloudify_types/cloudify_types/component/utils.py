# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import functools

from cloudify import ctx
from cloudify_types.utils import get_deployment_by_id

from .constants import CAPABILITIES


def no_rerun_on_resume(property_name):
    """Functions decorated with this, won't rerun when resumed

    When the function first returns, store its return value in runtime
    properties, under the given property_name. When it runs again, directly
    return that value, instead of running the function again.
    """

    def _deco(f):
        @functools.wraps(f)
        def _inner(*args, **kwargs):
            if property_name in ctx.instance.runtime_properties:
                return ctx.instance.runtime_properties[property_name]
            rv = f(*args, **kwargs)
            ctx.instance.runtime_properties[property_name] = rv
            ctx.instance.update()
            return rv
        return _inner
    return _deco


def deployment_id_exists(client, deployment_id):
    deployment = get_deployment_by_id(client, deployment_id)
    return True if deployment else False


def populate_runtime_with_wf_results(client,
                                     deployment_id,
                                     node_instance=None):
    if not node_instance:
        node_instance = ctx.instance
    ctx.logger.info('Fetching "%s" deployment capabilities..', deployment_id)

    if CAPABILITIES not in node_instance.runtime_properties:
        node_instance.runtime_properties[CAPABILITIES] = dict()

    ctx.logger.debug('Deployment ID is %s', deployment_id)
    response = client.deployments.capabilities.get(deployment_id)
    dep_capabilities = response.get(CAPABILITIES)
    node_instance.runtime_properties[CAPABILITIES] = dep_capabilities
    ctx.logger.info('Fetched capabilities:\n%s',
                    json.dumps(dep_capabilities, indent=1))

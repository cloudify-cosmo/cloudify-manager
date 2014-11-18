#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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


from jinja2 import Template
from config_constants import Constants


def create(ctx, policy_types, policy_triggers, groups, config_template):
    streams = []
    for group_name, group in groups.items():
        for policy_name, policy in group['policies'].items():
            template = Template(policy_types[policy['type']]['source'])
            metadata = {
                'group': group_name,
                'policy': policy_name,
                'policy_type': policy['type'],
                'members': group['members'],
                'ctx': ctx
            }
            template_vars = policy['properties']
            template_vars['_metadata'] = metadata
            data = template.render(**template_vars)
            streams.append({
                'data': data,
                'metadata': metadata
            })
    return Template(config_template).render(
        streams=streams,
        policy_triggers=policy_triggers,
        ctx=ctx,
        constants=Constants
    )

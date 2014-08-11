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

from collections import namedtuple

from jinja2 import Template


def _stream(data, metadata):
    return {
        'data': data,
        'metadata': metadata
    }


def create(policy_types, groups, config_template):
    streams = []
    for group_name, group in groups.items():
        node_name = group['members'][0]
        for policy_name, policy in group['policies'].items():
            template = Template(policy_types[policy['type']]['source'])
            template_properties = policy['properties']
            template_properties.update({
                'node_name': node_name
            })
            data = template.render(**template_properties)
            metadata = {
                'group': group_name,
                'policy': policy_name,
                'policy_type': policy['type'],
                'members': group['members']
            }
            streams.append(_stream(data, metadata))
    return Template(config_template).render(streams=streams)

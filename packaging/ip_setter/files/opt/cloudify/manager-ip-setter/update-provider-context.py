#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import json
import argparse

from sqlalchemy.orm.attributes import flag_modified

from manager_rest.flask_utils import setup_flask_app
from manager_rest.constants import PROVIDER_CONTEXT_ID
from manager_rest.storage import get_storage_manager, models


def update_provider_context(args):
    if args.networks:
        networks = json.load(args.networks)['networks']
    else:
        networks = None

    with setup_flask_app().app_context():
        sm = get_storage_manager()
        ctx = sm.get(models.ProviderContext, PROVIDER_CONTEXT_ID)
        agent_dict = ctx.context['cloudify']['cloudify_agent']
        if networks:
            for network_name, address in networks.items():
                previous_address = agent_dict['networks'].get(network_name)
                if previous_address and address != previous_address:
                    raise ValueError('Cannot change network {0} address'
                                     .format(network_name))
                else:
                    agent_dict['networks'][network_name]['manager'] = address
        agent_dict['broker_ip'] = args.manager_ip
        agent_dict['networks']['default']['manager'] = args.manager_ip
        flag_modified(ctx, 'context')
        sm.update(ctx)


parser = argparse.ArgumentParser()
parser.add_argument('--networks', type=argparse.FileType('r'),
                    help='File containing the manager networks dict. It '
                         'should be a JSON file containing an object with a '
                         '"networks" field.')
parser.add_argument('manager_ip',
                    help='The IP of this machine on the default network')
if __name__ == '__main__':
    args = parser.parse_args()
    update_provider_context(args)

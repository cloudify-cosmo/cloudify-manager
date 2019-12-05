#########
# Copyright (c) 2017-2019 Cloudify Platform Ltd. All rights reserved
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

from __future__ import print_function

import os
import argparse

from manager_rest import config
from manager_rest.storage import idencoder


def get_encoded_user_id(user_id):
    print(idencoder.get_encoder().encode(user_id))


if __name__ == '__main__':
    config_env_var = 'MANAGER_REST_SECURITY_CONFIG_PATH'
    if config_env_var not in os.environ:
        os.environ[config_env_var] = '/opt/manager/rest-security.conf'
    config.instance.load_configuration(from_db=False)

    # Not using click because the rest service doesn't have click in community
    parser = argparse.ArgumentParser(
        description='Get encoded form of user ID for API tokens.',
    )
    parser.add_argument(
        '-u', '--user-id',
        help='User ID to encode',
        type=int,
        required=True,
    )

    args = parser.parse_args()

    get_encoded_user_id(args.user_id)

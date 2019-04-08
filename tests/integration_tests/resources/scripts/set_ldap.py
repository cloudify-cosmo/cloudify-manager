########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

import os
import ast
import time
import socket
import argparse

from manager_rest import config
from manager_rest.flask_utils import setup_flask_app, set_admin_current_user


def set_ldap(config_dict):
    app = setup_flask_app()
    # mock current user, and reload rest configuration
    set_admin_current_user(app)
    config.instance.load_from_file("/opt/manager/cloudify-rest.conf")

    # Update the config table on manager DB to include LDAP configurations
    config.instance.update_db(config_dict)

    # Restart the rest service to load the new LDAP configuration
    os.system('systemctl stop cloudify-restservice')
    os.system('systemctl start cloudify-restservice')

    # wait for rest service to reload, up to 5 seconds
    end = time.time() + 5
    while not time.time() > end:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        p_open = sock.connect_ex(("localhost", 80)) == 0
        if p_open:
            break


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config')
    args = parser.parse_args()
    config_dict = ast.literal_eval(args.config)
    set_ldap(config_dict)

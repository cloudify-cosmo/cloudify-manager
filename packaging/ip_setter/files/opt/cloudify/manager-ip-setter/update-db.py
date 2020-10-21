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

import argparse
import os

from sqlalchemy.orm.attributes import flag_modified

from manager_rest.flask_utils import setup_flask_app
from manager_rest.storage import get_storage_manager, models

os.environ["MANAGER_REST_CONFIG_PATH"] = "/opt/manager/cloudify-rest.conf"
os.environ["MANAGER_REST_SECURITY_CONFIG_PATH"] = \
    "/opt/manager/rest-security.conf"
os.environ["MANAGER_REST_AUTHORIZATION_CONFIG_PATH"] = \
    "/opt/manager/authorization.conf"


def update_provider_context(args):
    with setup_flask_app().app_context():
        sm = get_storage_manager()
        for manager in sm.list(models.Manager):
            manager.private_ip = args.manager_ip
            manager.public_ip = args.manager_ip
            manager.networks['default'] = args.manager_ip
            flag_modified(manager, 'networks')
            sm.update(manager)
        for broker in sm.list(models.RabbitMQBroker):
            broker.host = args.manager_ip
            broker.networks['default'] = args.manager_ip
            flag_modified(broker, 'networks')
            sm.update(broker)
        for db in sm.list(models.DBNodes):
            db.host = args.manager_ip
            sm.update(db)


parser = argparse.ArgumentParser()
parser.add_argument('manager_ip',
                    help='The IP of this machine on the default network')
if __name__ == '__main__':
    args = parser.parse_args()
    update_provider_context(args)

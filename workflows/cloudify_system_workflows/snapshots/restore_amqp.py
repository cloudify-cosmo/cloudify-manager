########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from os import environ
from manager_rest.config import instance
from manager_rest.amqp_manager import AMQPManager
from manager_rest.flask_utils import setup_flask_app


environ['MANAGER_REST_CONFIG_PATH'] = '/opt/manager/cloudify-rest.conf'
app = setup_flask_app()

with app.app_context():
    instance.load_configuration()
    amqp_manager = AMQPManager(
        host=instance.amqp_host,
        username=instance.amqp_username,
        password=instance.amqp_password,
        verify=instance.amqp_ca_path
    )
    amqp_manager.sync_metadata()

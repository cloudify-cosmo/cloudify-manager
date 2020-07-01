#########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
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

import requests

from manager_rest import config

cfy_config = config.instance


def root_uri():
    prometheus_port = cfy_config.get('prometheus', {}).get('port')
    return 'http://localhost:{0}/monitoring/'.format(prometheus_port)


def credentials():
    if 'credentials' in cfy_config.get('prometheus'):
        prometheus_credentials = cfy_config.get('prometheus').get(
            'credentials')
        if ('username' in prometheus_credentials and
                'password' in prometheus_credentials):
            username = prometheus_credentials.get('username')
            password = prometheus_credentials.get('password')
            if username and password:
                return username, password
    services_to_install = cfy_config.get('services_to_install')
    if 'manager_service' in services_to_install:
        manager_credentials = cfy_config.get('manager', {}).get('security', {})
        return (manager_credentials.get('admin_username'),
                manager_credentials.get('admin_password'))
    if ('queue_service' in services_to_install and
            'username' in cfy_config.get('rabbitmq') and
            'password' in cfy_config.get('rabbitmq')):
        return (cfy_config.get('rabbitmq').get('username'),
                cfy_config.get('rabbitmq').get('password'))
    if ('database_service' in services_to_install and
            'postgres_password' in cfy_config.get('postgresql_server')):
        return ('postgres',
                cfy_config.get('postgresql_server').get('postgres_password'))
    return None


def get_alerts():
    alerts_uri = '{0}api/v1/alerts'.format(root_uri())
    r = requests.get(alerts_uri, auth=credentials())
    return r.json()

#!/usr/bin/env python
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
import subprocess


DEFAULT_CONF_PATH = '/etc/nginx/conf.d/cloudify.conf'
HTTP_PATH = '/etc/nginx/conf.d/http-external-rest-server.cloudify'
HTTPS_PATH = '/etc/nginx/conf.d/https-external-rest-server.cloudify'


parser = argparse.ArgumentParser()
parser.add_argument('--ssl-enabled', dest='ssl', action='store_true')
parser.add_argument('--ssl-disabled', dest='ssl', action='store_false')
parser.add_argument(
    '--service-management',
    dest='service_management',
    default='systemd',
)
parser.set_defaults(ssl=True)


def set_nginx_ssl(enabled):
    with open(DEFAULT_CONF_PATH) as f:
        config = f.read()
    if enabled:
        config = config.replace(HTTP_PATH, HTTPS_PATH)
    else:
        config = config.replace(HTTPS_PATH, HTTP_PATH)
    with open(DEFAULT_CONF_PATH, 'w') as f:
        f.write(config)


def restart_nginx(service_management):
    # wait one second before restarting nginx so that the caller has a chance
    # to clean up (this is most likely to be called from the REST service)
    if service_management == 'supervisord':
        subprocess.check_call([
            '/usr/bin/supervisorctl', '-c',
            '/etc/supervisord.conf', 'start', 'wait_on_restart'
        ])
    else:
        subprocess.check_call([
            '/usr/bin/systemd-run', '--on-active=1s',
            '--timer-property=AccuracySec=100ms',
            '/usr/bin/systemctl', 'restart', 'nginx'
        ])


if __name__ == '__main__':
    args = parser.parse_args()
    set_nginx_ssl(args.ssl)
    restart_nginx(args.service_management)

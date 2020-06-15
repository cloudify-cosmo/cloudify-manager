#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

import os
import socket

import yaml

from cloudify._compat import httplib, xmlrpclib
from cloudify.systemddbus import get_services
from cloudify.cluster_status import ServiceStatus, NodeServiceStatus


class UnixSocketHTTPConnection(httplib.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


class UnixSocketTransport(xmlrpclib.Transport, object):
    def __init__(self, path):
        super(UnixSocketTransport, self).__init__()
        self._path = path

    def make_connection(self, host):
        return UnixSocketHTTPConnection(self._path)


def read_from_yaml_file(file_path):
    with open(file_path, 'r') as f:
        file_content = f.read()
        try:
            return yaml.safe_load(file_content)
        except yaml.YAMLError as e:
            raise yaml.YAMLError('Failed to load yaml file {0}, due to '
                                 '{1}'.format(file_path, str(e)))


def _write_to_file(content, file_path):
    with open(file_path, 'w') as f:
        f.write(content)


def update_yaml_file(yaml_path, updated_content):
    if not isinstance(updated_content, dict):
        raise ValueError('Expected input of type dict, got {0} '
                         'instead'.format(type(updated_content)))
    if os.path.exists(yaml_path) and os.path.isfile(yaml_path):
        yaml_content = read_from_yaml_file(yaml_path)
    else:
        yaml_content = {}

    yaml_content.update(**updated_content)
    updated_file = yaml.safe_dump(yaml_content,
                                  default_flow_style=False)
    _write_to_file(updated_file, yaml_path)


def get_systemd_services(service_names):
    """
    :param service_names: {'service_unit_id': 'service_display_name'}
    e.g., {'cloudify-rabbitmq': 'RabbitMQ'}
    """

    def _get_services_with_suffix(_services):
        return {
            '{0}.service'.format(k): v for (k, v) in _services.items()
        }

    all_services = _get_services_with_suffix(service_names)
    systemd_services = get_services(all_services)
    statuses = []
    services = {}
    for service in systemd_services:
        is_service_running = service['instances'] and (
                service['instances'][0]['state'] == 'running')
        status = NodeServiceStatus.ACTIVE if is_service_running \
            else NodeServiceStatus.INACTIVE
        services[service['display_name']] = {
            'status': status,
            'extra_info': {
                'systemd': service
            }
        }
        statuses.append(status)
    return services, statuses


def get_supervisord_services(service_names):
    """
    :param service_names: {'service_id': 'service_display_name'}
    e.g., {'cloudify-rabbitmq': 'RabbitMQ'}
    """

    server = xmlrpclib.Server(
        'http://',
        transport=UnixSocketTransport("/tmp/supervisor.sock"))
    statuses = []
    services = {}
    for name, display_name in service_names.items():
        try:
            status_response = server.supervisor.getProcessInfo(name)
        except xmlrpclib.Fault as e:
            if e.faultCode == 10:
                service_status = NodeServiceStatus.INACTIVE
            else:
                raise
        else:
            if status_response['statename'] == 'RUNNING':
                service_status = NodeServiceStatus.ACTIVE
            else:
                service_status = NodeServiceStatus.INACTIVE
        statuses.append(service_status)
        services[display_name] = {
            'status': service_status,
            'is_remote': False,
            'extra_info': {}
        }
    return services, statuses


def determine_node_status(statuses):
    return (ServiceStatus.FAIL if NodeServiceStatus.INACTIVE in statuses
            else ServiceStatus.HEALTHY)

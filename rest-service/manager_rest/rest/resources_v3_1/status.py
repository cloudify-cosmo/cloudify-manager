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
#
import socket

from flask import request
from flask import current_app
from flask_restful_swagger import swagger

from cloudify.cluster_status import ServiceStatus, NodeServiceStatus
from cloudify._compat import httplib, xmlrpclib

from manager_rest import config
from manager_rest.rest import responses
from manager_rest.utils import get_amqp_client
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import verify_and_convert_bool
from manager_rest.syncthing_status_manager import get_syncthing_status
from manager_rest.rest.resources_v1.status import (
    should_be_in_services_output,
    get_system_manager_services
)

try:
    from cloudify.systemddbus import get_services
except ImportError:
    # For unit tests, currently systemd should be available on every manager
    get_services = None

try:
    from cloudify_premium import syncthing_utils
    from cloudify_premium.ha import utils as ha_utils
except ImportError:
    syncthing_utils = None
    ha_utils = None


BASE_SERVICES = {
    'nginx': 'Webserver',
    'cloudify-stage': 'Cloudify Console',
    'cloudify-amqp-postgres': 'AMQP-Postgres',
    'cloudify-mgmtworker': 'Management Worker',
    'cloudify-restservice': 'Manager Rest-Service'
}
OPTIONAL_SERVICES = {
    'postgresql-9.5': 'PostgreSQL',
    'cloudify-rabbitmq': 'RabbitMQ',
    'cloudify-composer': 'Cloudify Composer',
    'cloudify-syncthing': 'File Sync Service',
    'prometheus': 'Monitoring Service',
}


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


class Status(SecuredResource):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="status",
        notes="Returns state of the manager services"
    )
    @authorize('status_get')
    @marshal_with(responses.Status)
    def get(self):
        """Get the status of the manager services"""
        summary_response = verify_and_convert_bool(
            'summary',
            request.args.get('summary', False)
        )
        # Systemd should be available on every manager
        if not get_services:
            return {'status': ServiceStatus.FAIL, 'services': {}}

        services = {}
        if config.instance.service_management == 'supervisord':
            service_statuses = self._check_supervisord_services(services)
        else:
            service_statuses = self._check_systemd_services(services)
        rabbitmq_status = self._check_rabbitmq(services)

        # Passing our authentication implies PostgreSQL is healthy
        self._add_or_update_service(services, 'PostgreSQL',
                                    NodeServiceStatus.ACTIVE)

        syncthing_status = NodeServiceStatus.ACTIVE
        if ha_utils and ha_utils.is_clustered():
            syncthing_status = self._check_syncthing(services)

        status = self._get_manager_status(
            service_statuses,
            rabbitmq_status,
            syncthing_status
        )

        # If the response should be only the summary - mainly for LB
        if summary_response:
            return {'status': status, 'services': {}}

        return {'status': status, 'services': services}

    def _check_supervisord_services(self, services):
        statuses = []
        supervisord_services = get_system_manager_services(
            BASE_SERVICES,
            OPTIONAL_SERVICES
        )
        for name, display_name in supervisord_services.items():
            status = self._lookup_supervisor_service_status(name)
            if status:
                services[display_name] = {
                    'status': status,
                    'is_remote': False,
                    'extra_info': {}
                }
                statuses.append(status)
        return statuses

    def _check_systemd_services(self, services):
        def _get_services_with_suffix(_services):
            return {
                '{0}.service'.format(k): v for (k, v) in _services.items()
            }
        all_services = get_system_manager_services(
            BASE_SERVICES,
            OPTIONAL_SERVICES
        )
        all_services = _get_services_with_suffix(all_services)
        systemd_services = get_services(all_services)
        statuses = []
        for service in systemd_services:
            status = self._lookup_systemd_service_status(
                service, _get_services_with_suffix(OPTIONAL_SERVICES)
            )
            if status:
                services[service['display_name']] = {
                    'status': status,
                    'is_remote': False,
                    'extra_info': {
                        'systemd': service
                    }
                }
                statuses.append(status)
        return statuses

    def _lookup_systemd_service_status(self, service, optional_services):
        status = None
        if should_be_in_services_output(service, optional_services):
            is_service_running = service['instances'] and (
                    service['instances'][0]['state'] == 'running')
            status = NodeServiceStatus.ACTIVE if is_service_running \
                else NodeServiceStatus.INACTIVE

        return status

    def _lookup_supervisor_service_status(self, service_name):
        service_status = None
        is_optional = True if service_name in OPTIONAL_SERVICES else False
        server = xmlrpclib.Server(
            'http://',
            transport=UnixSocketTransport("/tmp/supervisor.sock"))
        try:
            status_response = server.supervisor.getProcessInfo(service_name)
        except xmlrpclib.Fault as e:
            # If the error is raised that means one of the two options:
            # 1. The service is optional and not installed (faultCode=10)
            # ignore the error
            # 2. The service is either optional/required and return
            # faultCode other than 10 that need to raise error
            if e.faultCode == 10:
                if not is_optional:
                    service_status = NodeServiceStatus.INACTIVE
            else:
                raise

        else:
            service_status = status_response['statename']
            if service_status == 'RUNNING':
                service_status = NodeServiceStatus.ACTIVE

        return service_status

    def _check_rabbitmq(self, services):
        name = 'RabbitMQ'
        client = get_amqp_client()
        try:
            with client:
                extra_info = {'connection_check': ServiceStatus.HEALTHY}
                self._add_or_update_service(services,
                                            name,
                                            NodeServiceStatus.ACTIVE,
                                            extra_info=extra_info)
                return NodeServiceStatus.ACTIVE
        except Exception as err:
            error_message = 'Broker check failed with {err_type}: ' \
                            '{err_msg}'.format(err_type=type(err),
                                               err_msg=str(err))
            current_app.logger.error(error_message)
            extra_info = {'connection_check': error_message}
            self._add_or_update_service(services,
                                        name,
                                        NodeServiceStatus.INACTIVE,
                                        extra_info=extra_info)
            return NodeServiceStatus.INACTIVE

    def _check_syncthing(self, services):
        display_name = 'File Sync Service'
        status, extra_info = get_syncthing_status()
        self._add_or_update_service(services, display_name, status,
                                    extra_info=extra_info)
        return status

    def _get_manager_status(self, systemd_statuses, rabbitmq_status,
                            syncthing_status):
        statuses = systemd_statuses + [rabbitmq_status, syncthing_status]
        return (ServiceStatus.FAIL if NodeServiceStatus.INACTIVE in statuses
                else ServiceStatus.HEALTHY)

    def _add_or_update_service(self, services, display_name, status,
                               extra_info=None):
        # If this service is remote it doesn't exist in services dict yet
        services.setdefault(display_name, {'is_remote': True})
        services[display_name].update({'status': status})
        if extra_info:
            services[display_name].setdefault('extra_info', {})
            services[display_name]['extra_info'].update(extra_info)

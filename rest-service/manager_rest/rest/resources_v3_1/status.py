import socket
import http.client
import xmlrpc.client
from typing import Dict

from flask import request
from flask import current_app
from flask_restful import Resource

from cloudify.cluster_status import ServiceStatus, NodeServiceStatus

from manager_rest import config
from manager_rest.rest import responses, swagger
from manager_rest.utils import get_amqp_client
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.rest.rest_utils import verify_and_convert_bool
from manager_rest.syncthing_status_manager import get_syncthing_status

try:
    from cloudify_premium.ha import utils as ha_utils
except ImportError:
    ha_utils = None


BASE_SERVICES = {
    'nginx': 'Webserver',
    'cloudify-amqp-postgres': 'AMQP-Postgres',
    'cloudify-mgmtworker': 'Management Worker',
    'cloudify-restservice': 'Manager Rest-Service',
    'cloudify-api': 'Cloudify API',
    'cloudify-execution-scheduler': 'Cloudify Execution Scheduler',
}
OPTIONAL_SERVICES = {
    'cloudify-stage': 'Cloudify Console',
    'haproxy': 'Haproxy for DB HA',
    'patroni': 'Patroni HA Postgres',
    'postgresql-14': 'PostgreSQL',
    'cloudify-rabbitmq': 'RabbitMQ',
    'cloudify-composer': 'Cloudify Composer',
    'cloudify-syncthing': 'File Sync Service',
    'prometheus': 'Monitoring Service',
}


class UnixSocketHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.host)


class UnixSocketTransport(xmlrpc.client.Transport, object):
    def __init__(self, path):
        super(UnixSocketTransport, self).__init__()
        self._path = path

    def make_connection(self, host):
        return UnixSocketHTTPConnection(self._path)


class OK(Resource):
    @swagger.operation(
        nickname="ok",
        notes="Returns 200/OK if the manager is healthy, 500/FAIL otherwise.",
    )
    def get(self):
        """Return OK if the manager is healthy, unauthenticated.
        Don't give any more details if the manager is not healthy, because the
        endpoint is not authenticated.
        This is intended for load balancers and the cluster status.
        """
        status, _ = _get_status_and_services()

        if status == ServiceStatus.HEALTHY:
            return "OK", 200
        else:
            return "FAIL", 500


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
        status, services = _get_status_and_services()

        if summary_response:
            return {'status': status, 'services': {}}

        return {'status': status, 'services': services}


def _get_status_and_services():
    services: Dict[str, Dict] = {}
    service_statuses = _check_supervisord_services(services)
    rabbitmq_status = _check_rabbitmq(services)

    # Successfully making any query requires us to check the DB is up
    # (for the cope_with_db_failover logic), so we can assume postgres
    # is healthy if we reach here.
    _add_or_update_service(services, 'PostgreSQL',
                           NodeServiceStatus.ACTIVE)

    if isinstance(config.instance.postgresql_host, list):
        services.pop('PostgreSQL')
        service_statuses = [
            service['status'] for service in services.values()
        ]

    syncthing_status = NodeServiceStatus.ACTIVE
    if ha_utils and ha_utils.is_clustered():
        syncthing_status = _check_syncthing(services)

    status = _get_manager_status(
        service_statuses,
        rabbitmq_status,
        syncthing_status
    )

    return status, services


def _check_supervisord_services(services):
    statuses = []
    supervisord_services = get_system_manager_services(
        BASE_SERVICES,
        OPTIONAL_SERVICES
    )
    for name, display_name in supervisord_services.items():
        status = _lookup_supervisor_service_status(name)
        if status:
            services[display_name] = {
                'status': status,
                'is_remote': False,
                'extra_info': {}
            }
            statuses.append(status)
    return statuses


def _lookup_supervisor_service_status(service_name):
    service_status = None
    is_optional = True if service_name in OPTIONAL_SERVICES else False
    server = xmlrpc.client.Server(
        'http://',
        transport=UnixSocketTransport("/var/run/supervisord.sock"))
    try:
        status_response = server.supervisor.getProcessInfo(service_name)
    except xmlrpc.client.Fault as e:
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
    except FileNotFoundError:
        service_status = NodeServiceStatus.INACTIVE
    else:
        if not isinstance(status_response, dict):
            raise RuntimeError(
                f'unexpected status_response: {status_response!r}')
        service_status = status_response['statename']
        if service_status == 'RUNNING':
            service_status = NodeServiceStatus.ACTIVE
        else:
            service_status = NodeServiceStatus.INACTIVE

    return service_status


def _check_rabbitmq(services):
    name = 'RabbitMQ'
    try:
        with get_amqp_client(connect_timeout=3):
            extra_info = {'connection_check': ServiceStatus.HEALTHY}
            _add_or_update_service(services,
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
        _add_or_update_service(services,
                               name,
                               NodeServiceStatus.INACTIVE,
                               extra_info=extra_info)
        return NodeServiceStatus.INACTIVE


def _check_syncthing(services):
    display_name = 'File Sync Service'
    status, extra_info = get_syncthing_status()
    _add_or_update_service(services, display_name, status, extra_info)
    return status


def _get_manager_status(systemd_statuses, rabbitmq_status, syncthing_status):
    statuses = systemd_statuses + [rabbitmq_status, syncthing_status]
    return (ServiceStatus.FAIL if NodeServiceStatus.INACTIVE in statuses
            else ServiceStatus.HEALTHY)


def _add_or_update_service(services, display_name, status, extra_info=None):
    # If this service is remote it doesn't exist in services dict yet
    services.setdefault(display_name, {'is_remote': True})
    services[display_name].update({'status': status})
    if extra_info:
        services[display_name].setdefault('extra_info', {})
        services[display_name]['extra_info'].update(extra_info)


def get_system_manager_services(base_services, optional_services):
    """Services the status of which we keep track of.
    :return: a dict of {service_name: label}
    """
    services = {}

    # Use updates to avoid mutating the 'constant'
    services.update(base_services)
    services.update(optional_services)

    return services

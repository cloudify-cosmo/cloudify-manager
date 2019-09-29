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

from datetime import datetime, timedelta

from flask import request
from flask import current_app
from flask_restful_swagger import swagger

from manager_rest.rest import responses
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security import SecuredResourceReadonlyMode
from manager_rest.rest.rest_utils import (
    parse_datetime_string,
    verify_and_convert_bool
)
from manager_rest.rest.resources_v1.status import (
    broker_is_healthy,
    should_be_in_services_output,
    get_systemd_manager_services
)

try:
    from manager_rest.systemddbus import get_services
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
    'nginx.service': 'Webserver',
    'cloudify-stage.service': 'Cloudify Console',
    'cloudify-amqp-postgres.service': 'AMQP-Postgres',
    'cloudify-mgmtworker.service': 'Management Worker',
    'cloudify-restservice.service': 'Manager Rest-Service'
}
OPTIONAL_SERVICES = {
    'postgresql-9.5.service': 'PostgreSQL',
    'cloudify-rabbitmq.service': 'RabbitMQ',
    'cloudify-composer.service': 'Cloudify Composer',
    'cloudify-syncthing.service': 'File Sync Service'
}
ACTIVE_STATE = 'Active'
INACTIVE_STATE = 'Inactive'
HEALTHY_STATE = 'OK'
FAIL_STATE = 'FAIL'


class Status(SecuredResourceReadonlyMode):

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
            return {'status': FAIL_STATE, 'services': {}}

        services = {}
        systemd_statuses = self._check_systemd_services(services)
        rabbitmq_status = self._check_rabbitmq(services)

        # Passing our authentication implies PostgreSQL is healthy
        self._add_or_update_service(services, 'PostgreSQL', ACTIVE_STATE)

        syncthing_status = ACTIVE_STATE
        if ha_utils and ha_utils.is_clustered():
            syncthing_status = self._check_syncthing(services)

        status = self._get_manager_status(systemd_statuses, rabbitmq_status,
                                          syncthing_status)

        # If the response should be only the summary - mainly for LB
        if summary_response:
            return {'status': status, 'services': {}}

        return {'status': status, 'services': services}

    def _check_systemd_services(self, services):
        systemd_services = get_services(
            get_systemd_manager_services(BASE_SERVICES, OPTIONAL_SERVICES)
        )
        statuses = []
        for service in systemd_services:
            if should_be_in_services_output(service, OPTIONAL_SERVICES):
                status = ACTIVE_STATE if service['instances'][0]['state'] == \
                                         'running' else INACTIVE_STATE
                services[service['display_name']] = {
                    'status': status,
                    'is_external': False,
                    'extra_info': {
                        'systemd': service
                    }
                }
                statuses.append(status)
        return statuses

    def _check_rabbitmq(self, services):
        broker_status = ACTIVE_STATE if broker_is_healthy() else INACTIVE_STATE
        self._add_or_update_service(services, 'RabbitMQ', broker_status)
        return broker_status

    def _check_syncthing(self, services):
        status = INACTIVE_STATE
        display_name = 'File Sync Service'

        try:
            syncthing_config = syncthing_utils.config()
            device_stats = syncthing_utils.device_stats()
        except Exception as err:
            current_app.logger.error(
                'Syncthing check failed with {err_type}: {err_msg}'.format(
                    err_type=type(err),
                    err_msg=str(err),
                )
            )
            self._add_or_update_service(services, display_name, status)
            return status

        # Add 1 second to the interval for avoiding false negative
        interval = syncthing_config['options']['reconnectionIntervalS'] + 1
        min_last_seen = datetime.utcnow() - timedelta(seconds=interval)

        for device_id, stats in device_stats.items():
            last_seen = parse_datetime_string(stats['lastSeen'])

            # Syncthing is valid when at least one device was seen recently
            if last_seen > min_last_seen:
                status = ACTIVE_STATE
                break

        self._add_or_update_service(services, display_name, status)
        return status

    def _get_manager_status(self, systemd_statuses, rabbitmq_status,
                            syncthing_status):
        statuses = systemd_statuses + [rabbitmq_status, syncthing_status]
        return FAIL_STATE if INACTIVE_STATE in statuses else HEALTHY_STATE

    def _add_or_update_service(self, services, display_name, status):
        # If this service is external it doesn't exist in services dict yet
        services.setdefault(display_name, {'is_external': True})
        services[display_name].update({'status': status})

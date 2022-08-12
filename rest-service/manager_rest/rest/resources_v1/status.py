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
#

from flask import current_app
from flask_restful_swagger import swagger

from manager_rest import config
from manager_rest.rest import responses
from manager_rest.utils import get_amqp_client
from manager_rest.security import SecuredResource
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security.authorization import authorize
try:
    from cloudify.systemddbus import get_services
except ImportError:
    get_services = None

BASE_SERVICES = {
    'cloudify-mgmtworker.service': 'Management Worker',
    'cloudify-restservice.service': 'Manager Rest-Service',
    'cloudify-rabbitmq.service': 'RabbitMQ',
    'cloudify-amqp-postgres.service': 'AMQP-Postgres',
    'nginx.service': 'Webserver',
    'postgresql-14.service': 'PostgreSQL'
}
OPTIONAL_SERVICES = {
    'cloudify-stage.service': 'Cloudify Console',
    'cloudify-composer.service': 'Cloudify Composer',
}


class Status(SecuredResource):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="status",
        notes="Returns state of running system services"
    )
    @authorize('status_get')
    @marshal_with(responses.Status)
    def get(self, **kwargs):
        """Get the status of running system services"""
        if get_services:
            services = get_system_manager_services(BASE_SERVICES,
                                                   OPTIONAL_SERVICES)
            jobs = get_services(services)
            jobs = [
                job for job in jobs
                if should_be_in_services_output(job, OPTIONAL_SERVICES)
            ]
            # If PostgreSQL is not local, print it as 'remote'
            if not config.instance.postgresql_host.startswith(('localhost',
                                                               '127.0.0.1')):
                for job in jobs:
                    if job['display_name'] == 'PostgreSQL' \
                            and job['instances']:
                        job['instances'][0]['state'] = 'remote'

            broker_state = 'running' if broker_is_healthy() else 'failed'
            for job in jobs:
                if job['display_name'] == 'RabbitMQ' and job['instances']:
                    job['instances'][0]['state'] = broker_state
        else:
            jobs = ['undefined']

        return {'status': 'running', 'services': jobs}


def should_be_in_services_output(job, optional_services):
    if job['unit_id'] not in optional_services:
        return True

    if job['instances']:
        # We have some details of the systemd job...
        if job['instances'][0]['LoadState'] != 'not-found':
            # And since its LoadState wasn't not-found, it should be
            # installed and working
            return True

    # If we reach here then the service is optional and not installed
    return False


def get_system_manager_services(base_services, optional_services):
    """Services the status of which we keep track of.
    :return: a dict of {service_name: label}
    """
    services = {}

    # Use updates to avoid mutating the 'constant'
    services.update(base_services)
    services.update(optional_services)

    return services


def broker_is_healthy():
    client = get_amqp_client()
    try:
        with client:
            return True
    except Exception as err:
        current_app.logger.error(
            'Broker check failed with {err_type}: {err_msg}'.format(
                err_type=type(err),
                err_msg=str(err),
            )
        )
        return False

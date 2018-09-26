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
#
from flask_restful_swagger import swagger
from opentracing_instrumentation.request_context import get_current_span, \
    span_in_context

from manager_rest import config
from manager_rest.rest import responses, rest_utils
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with
)
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
try:
    from manager_rest.systemddbus import get_services
except ImportError:
    get_services = None

BASE_SERVICES = {
    'cloudify-mgmtworker.service': 'Management Worker',
    'cloudify-restservice.service': 'Manager Rest-Service',
    'cloudify-rabbitmq.service': 'RabbitMQ',
    'cloudify-amqp-postgres.service': 'AMQP-Postgres',
    'nginx.service': 'Webserver',
    'postgresql-9.5.service': 'PostgreSQL'
}
OPTIONAL_SERVICES = {
    'cloudify-influxdb.service': 'InfluxDB',
    'cloudify-riemann.service': 'Riemann',
    'cloudify-amqpinflux.service': 'AMQP InfluxDB',
    'cloudify-stage.service': 'Cloudify Console',
    'cloudify-composer.service': 'Cloudify Composer',
}
CLUSTER_SERVICES = {
    'cloudify-postgresql.service': 'PostgreSQL',
    'cloudify-consul.service': 'Consul',
    'cloudify-syncthing.service': 'Syncthing',
}


class Status(SecuredResource):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="status",
        notes="Returns state of running system services"
    )
    @exceptions_handled
    @authorize('status_get')
    @marshal_with(responses.Status)
    def get(self, **kwargs):
        """Get the status of running system services"""
        span = get_current_span()
        if get_services:
            with span_in_context(span):
                jobs = get_services(self._get_systemd_manager_services())
                jobs = [
                    job for job in jobs
                    if self._should_be_in_services_output(job)
                ]
            # If PostgreSQL is not local, print it as 'remote'
            if not config.instance.postgresql_host.startswith(
                    ('localhost', '127.0.0.1')):
                for job in jobs:
                    if job['display_name'] == 'PostgreSQL':
                        job['instances'][0]['state'] = 'remote'
        else:
            jobs = ['undefined']
        span.set_tag('services', jobs)
        return {'status': 'running', 'services': jobs}

    def _should_be_in_services_output(self, job):
        if job['unit_id'] not in OPTIONAL_SERVICES:
            return True

        if job['instances']:
            # We have some details of the systemd job...
            if job['instances'][0]['LoadState'] != 'not-found':
                # And since its LoadState wasn't not-found, it should be
                # installed and working
                return True

        # If we reach here then the service is optional and not installed
        return False

    def _get_systemd_manager_services(self):
        """Services the status of which we keep track of.

        :return: a dict of {service_name: label}
        """
        services = {}

        # Use updates to avoid mutating the 'constant'
        services.update(BASE_SERVICES)
        services.update(OPTIONAL_SERVICES)

        if rest_utils.is_clustered():
            # clustered postgresql service is named differently -
            # the old service is not used in a clustered manager,
            # so we can ignore its status
            del services['postgresql-9.5.service']

            # services that are only running in a clustered manager
            services.update(CLUSTER_SERVICES)
        return services

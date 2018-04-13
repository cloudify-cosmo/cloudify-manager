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

from manager_rest.rest import responses, rest_utils
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
try:
    from manager_rest.systemddbus import get_services
except ImportError:
    get_services = None

BASE_SERVICES = {
    'cloudify-mgmtworker.service': 'Celery Management',
    'cloudify-restservice.service': 'Manager Rest-Service',
    'cloudify-rabbitmq.service': 'RabbitMQ',
    'logstash.service': 'Logstash',
    'nginx.service': 'Webserver',
    'postgresql-9.5.service': 'PostgreSQL'
}
OPTIONAL_SERVICES = {
    'cloudify-influxdb.service': 'InfluxDB',
    'cloudify-riemann.service': 'Riemann',
    'cloudify-amqpinflux.service': 'AMQP InfluxDB',
    'cloudify-stage.service': 'Cloudify Stage',
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
        if get_services:
            jobs = get_services(self._get_systemd_manager_services())
            jobs = [
                job for job in jobs
                # Don't display optional services if they don't exist
                if (
                    job['instances']
                    or job['unit_id'] not in OPTIONAL_SERVICES
                )
            ]
        else:
            jobs = ['undefined']

        return {'status': 'running', 'services': jobs}

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

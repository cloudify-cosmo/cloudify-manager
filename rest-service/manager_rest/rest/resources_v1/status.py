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

import os

from flask_restful_swagger import swagger

from manager_rest.rest import responses
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)
from manager_rest.security import SecuredResource
try:
    from cloudify_premium.ha import node_status
except ImportError:
    node_status = {'initialized': False}


class Status(SecuredResource):

    @swagger.operation(
        responseClass=responses.Status,
        nickname="status",
        notes="Returns state of running system services"
    )
    @exceptions_handled
    @marshal_with(responses.Status)
    def get(self, **kwargs):
        """
        Get the status of running system services
        """
        try:
            if self._is_docker_env():
                job_list = {'riemann': 'Riemann',
                            'rabbitmq-server': 'RabbitMQ',
                            'celeryd-cloudify-management': 'Celery Management',
                            'cloudify-ui': 'Cloudify UI',
                            'logstash': 'Logstash',
                            'nginx': 'Webserver',
                            'rest-service': 'Manager Rest-Service',
                            'amqp-influx': 'AMQP InfluxDB'
                            }
                from manager_rest.runitsupervise import get_services
                jobs = get_services(job_list)
            else:
                from manager_rest.systemddbus import get_services
                job_list = {'cloudify-mgmtworker.service': 'Celery Management',
                            'cloudify-restservice.service':
                                'Manager Rest-Service',
                            'cloudify-amqpinflux.service': 'AMQP InfluxDB',
                            'cloudify-influxdb.service': 'InfluxDB',
                            'cloudify-rabbitmq.service': 'RabbitMQ',
                            'cloudify-riemann.service': 'Riemann',
                            'cloudify-stage.service': 'Cloudify Stage',
                            'logstash.service': 'Logstash',
                            'nginx.service': 'Webserver',
                            'postgresql-9.5.service': 'PostgreSQL'
                            }

                if self._is_clustered():
                    # clustered postgresql service is named differently -
                    # the old service is not used in a clustered manager,
                    # so we can ignore its status
                    del job_list['postgresql-9.5.service']

                    # services that are only running in a clustered manager
                    job_list.update({
                        'cloudify-postgresql.service': 'PostgreSQL',
                        'cloudify-consul.service': 'Consul',
                        'cloudify-syncthing.service': 'Syncthing',
                    })

                jobs = get_services(job_list)
        except ImportError:
            jobs = ['undefined']

        return dict(status='running', services=jobs)

    @staticmethod
    def _is_docker_env():
        return os.getenv('DOCKER_ENV') is not None

    @staticmethod
    def _is_clustered():
        return node_status.get('initialized')

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


def alerts(root_uri):
    """
    Get list of pending or firing alerts from Prometheus.
    Returns a list of alerts in case of successful communication, empty list
    otherwise.
    """
    alerts_uri = '{0}api/v1/alerts'.format(root_uri)
    r = requests.get(alerts_uri)
    if r.status_code == requests.codes.ok and 'data' in r.json():
        return r.json()['data'].get('alerts', [])
    return []


def query(query_string, root_uri, ca_cert=None):
    # Results like:
    # {
    #     "data": {
    #         "result": [
    #             {
    #                 "metric": {
    #                     "__name__": "up",
    #                     "instance": "172.22.0.5:53333",
    #                     "job": "federate_postgresql"
    #                 },
    #                 "value": [
    #                     1594192345.589,
    #                     "1"
    #                 ]
    #             },
    #             {
    #                 "metric": {
    #                     "__name__": "up",
    #                     "instance": "172.22.0.6:53333",
    #                     "job": "federate_postgresql"
    #                 },
    #                 "value": [
    #                     1594192345.589,
    #                     "1"
    #                 ]
    #             },
    #             {
    #                 "metric": {
    #                     "__name__": "up",
    #                     "instance": "172.22.0.7:53333",
    #                     "job": "federate_postgresql"
    #                 },
    #                 "value": [
    #                     1594192345.589,
    #                     "1"
    #                 ]
    #             }
    #         ],
    #         "resultType": "vector"
    #     },
    #     "status": "success"
    # }
    #
    # or
    #
    # {
    #     "data": {
    #         "result": [
    #             {
    #                 "metric": {
    #                     "__name__": "up",
    #                     "instance": "172.22.0.8:53333",
    #                     "job": "federate_rabbitmq"
    #                 },
    #                 "value": [
    #                     1594193908.009,
    #                     "1"
    #                 ]
    #             },
    #             {
    #                 "metric": {
    #                     "__name__": "up",
    #                     "instance": "172.22.0.9:53333",
    #                     "job": "federate_rabbitmq"
    #                 },
    #                 "value": [
    #                     1594193908.009,
    #                     "1"
    #                 ]
    #             }
    #         ],
    #         "resultType": "vector"
    #     },
    #     "status": "success"
    # }
    #
    # or
    #
    # {
    #     "data": {
    #         "result": [],
    #         "resultType": "vector"
    #     },
    #     "status": "success"
    # }
    #
    # or
    #
    # {
    #     "status": "success",
    #     "data": {
    #         "resultType": "vector",
    #         "result":
    #             [
    #                 {
    #                     "metric": {
    #                         "__name__": "up",
    #                         "instance": "localhost:9187",
    #                         "job": "postgresql"
    #                     },
    #                     "value": [
    #                         1594194015.187,
    #                         "1"
    #                     ]
    #                 }
    #             ]
    #     }
    # }
    #
    # or
    #
    # {"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"up","instance":"localhost:15692","job":"rabbitmq"},"value":[1594194194.605,"1"]}]}}
    #
    # or
    #
    # {"status":"success","data":{"resultType":"vector","result":[{"metric":{"__name__":"up","instance":"http://10.0.1.119/","job":"http_200"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"http://127.0.0.1:3000/","job":"http_200"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"http://10.0.1.119:80/","job":"http_200"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"http://127.0.0.1:8088/","job":"http_200"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"http://127.0.0.1:8100/api/v3.1/status","job":"http_40x"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"http://127.0.0.1:53229/","job":"http_40x"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"http://10.0.1.119/composer","job":"http_200"},"value":[1594194226.929,"1"]},{"metric":{"__name__":"up","instance":"https://10.0.1.119:53333/","job":"http_200"},"value":[1594194226.929,"1"]}]}}
    params = {'query': query_string}
    query_uri = '{0}api/v1/query'.format(root_uri)
    try:
        r = requests.get(query_uri,
                         params=params,
                         verify=ca_cert if ca_cert else True)
    except requests.exceptions.ConnectionError:
        return []
    result, result_type = _format_prometheus_response(r)
    if result_type == 'vector':
        return result
    return []


def healthy_postgresql_nodes(root_uri):
    """
    Get number of healthy PostgreSQL nodes (in a cluster).
    Prometheus response would look like this:
    {
        "data": {
            "result": [
                {
                    "metric": {
                        "job": "federate_postgresql"
                    },
                    "value": [
                        1594058904.181,
                        "3"
                    ]
                }
            ],
            "resultType": "vector"
        },
        "status": "success"
    }
    """
    params = {'query': 'sum by (job) (up{job="federate_postgresql"} and '
                       'pg_up{job="federate_postgresql"})'}
    query_uri = '{0}api/v1/query'.format(root_uri)
    r = requests.get(query_uri, params=params)
    return _value_from_prometheus_response(r)


def healthy_rabbitmq_nodes(root_uri):
    """
    Get number of healthy RabbitMQ nodes (in a cluster).
    Prometheus response would look like this:
    {
        "data": {
            "result": [
                {
                    "metric": {
                        "job": "federate_rabbitmq"
                    },
                    "value": [
                        1594059512.841,
                        "2"
                    ]
                }
            ],
            "resultType": "vector"
        },
        "status": "success"
    }
    """
    params = {'query': 'sum by (job) (up{job="federate_rabbitmq"})'}
    query_uri = '{0}api/v1/query'.format(root_uri)
    r = requests.get(query_uri, params=params)
    return _value_from_prometheus_response(r)


def _format_prometheus_response(response):
    if response.status_code == requests.codes.ok and 'data' in response.json():
        response_data = response.json()['data']
        if 'result' in response_data and 'resultType' in response_data:
            return response_data['result'], response_data['resultType'],
    return None, None


def _value_from_prometheus_response(response):
    if response.status_code == requests.codes.ok and 'data' in response.json():
        result = response.json()['data'].get('result', [])
        if len(result) > 0:
            value = result[0].get('value', [])
            if len(value) == 2:
                return int(value[1])
    return -1

#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

import json
import types
import urllib
from datetime import datetime

from functools import wraps

from manager_rest import utils, manager_exceptions
from cloudify_rest_client.client import HTTPClient
from cloudify_rest_client.executions import Execution
from manager_rest.storage import get_storage_manager, models, get_node
from manager_rest.storage.models import (Node,
                                         Blueprint,
                                         Deployment,
                                         NodeInstance,
                                         License)

try:
    from cloudify_rest_client.client import \
        DEFAULT_API_VERSION as CLIENT_API_VERSION
except ImportError:
    CLIENT_API_VERSION = 'v1'


def build_query_string(query_params):
    query_string = ''
    if query_params and len(query_params) > 0:
        query_string += urllib.urlencode(query_params, True) + '&'
    return query_string


def mock_authorize(action):
    def authorize_dec(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return authorize_dec


class MockClientResponse(object):
    def __init__(self, response):
        self.json = lambda: self._to_json(response.json)
        self.status_code = response.status_code
        self.content = response.content

    @staticmethod
    def _to_json(json_source):
        if json_source:
            return json_source
        raise Exception('This is mocked behavior as client\'s response')


class MockHTTPClient(HTTPClient):

    def __init__(self, app, headers=None, file_server=None):
        super(MockHTTPClient, self).__init__(host='localhost',
                                             headers=headers)
        self.app = app
        self._file_server = file_server

    def do_request(self,
                   requests_method,
                   uri,
                   data=None,
                   params=None,
                   headers=None,
                   pagination=None,
                   sort=None,
                   expected_status_code=200,
                   stream=False,
                   versioned_url=True,
                   timeout=None):
        if CLIENT_API_VERSION == 'v1':
            # in v1, HTTPClient won't append the version part of the URL
            # on its own, so it's done here instead
            uri = '/api/{0}{1}'.format(CLIENT_API_VERSION, uri)

        return super(MockHTTPClient, self).do_request(
            requests_method=requests_method,
            uri=uri,
            data=data,
            params=params,
            headers=headers,
            expected_status_code=expected_status_code,
            stream=stream
        )

    def _do_request(self, requests_method, request_url, body, params, headers,
                    expected_status_code, stream, verify, timeout=None):
        if 'get' in requests_method.__name__:
            response = self.app.get(request_url,
                                    headers=headers,
                                    data=body,
                                    query_string=build_query_string(params))

        elif 'put' in requests_method.__name__:
            if isinstance(body, types.GeneratorType):
                body = ''.join(body)
            response = self.app.put(request_url,
                                    headers=headers,
                                    data=body,
                                    query_string=build_query_string(params))
        elif 'post' in requests_method.__name__:
            if isinstance(body, types.GeneratorType):
                body = ''.join(body)
            response = self.app.post(request_url,
                                     headers=headers,
                                     data=body,
                                     query_string=build_query_string(params))
        elif 'patch' in requests_method.__name__:
            response = self.app.patch(request_url,
                                      headers=headers,
                                      data=body,
                                      query_string=build_query_string(params))
        elif 'delete' in requests_method.__name__:
            response = self.app.delete(request_url,
                                       headers=headers,
                                       data=body,
                                       query_string=build_query_string(params))
        else:
            raise NotImplementedError()

        if response.status_code != expected_status_code:
            response.content = response.data
            self._raise_client_error(MockClientResponse(response), request_url)

        if stream:
            return MockStreamedResponse(response, self._file_server)

        if expected_status_code == 204:
            return None

        return json.loads(response.data)


class MockStreamedResponse(object):

    def __init__(self, response, file_server):
        self._response = response
        self._root = file_server.root_path

    @property
    def headers(self):
        return self._response.headers

    def bytes_stream(self, chunk_size=8192):
        # Calculate where the file resides *locally*
        local_path = self._response.headers['X-Accel-Redirect'].replace(
            '/resources',
            self._root
        )
        return self._generate_stream(local_path, chunk_size)

    @staticmethod
    def _generate_stream(local_path, chunk_size):
        with open(local_path, 'rb') as local_file:
            while True:
                chunk = local_file.read(chunk_size)
                if chunk:
                    yield chunk
                else:
                    break

    def close(self):
        self._response.close()


def task_state():
    """ This is a function in order to allow mocking it in some tests """
    return Execution.TERMINATED


def mock_execute_task(execution_id, **_):
    sm = get_storage_manager()
    execution = sm.get(models.Execution, execution_id)
    execution.status = task_state()
    execution.ended_at = utils.get_formatted_timestamp()
    execution.error = ''
    sm.update(execution)


def put_node_instance(storage_manager,
                      instance_id,
                      deployment_id,
                      runtime_properties=None,
                      node_id='node_id',
                      version=None,
                      blueprint_id='blueprint_id',
                      index=None):
    runtime_properties = runtime_properties or {}
    index = index or 1

    blueprint = _get_or_create_blueprint(storage_manager, blueprint_id)
    deployment = _get_or_create_deployment(storage_manager,
                                           deployment_id,
                                           blueprint)
    node = _get_or_create_node(storage_manager, node_id, deployment)
    node_instance = NodeInstance(
        id=instance_id,
        runtime_properties=runtime_properties,
        state='',
        version=version,
        relationships=None,
        host_id=None,
        scaling_groups=None
    )
    node_instance.node = node
    return storage_manager.put(node_instance)


def _get_or_create_blueprint(storage_manager, blueprint_id):
    try:
        return storage_manager.get(Blueprint, blueprint_id)
    except manager_exceptions.NotFoundError:
        blueprint = Blueprint(
            id=blueprint_id,
            created_at=datetime.now(),
            main_file_name='',
            plan={}
        )
        return storage_manager.put(blueprint)


def _get_or_create_deployment(storage_manager, deployment_id, blueprint):
    try:
        return storage_manager.get(Deployment, deployment_id)
    except manager_exceptions.NotFoundError:
        deployment = Deployment(
            id=deployment_id,
            created_at=datetime.now()
        )
        deployment.blueprint = blueprint
        return storage_manager.put(deployment)


def _get_or_create_node(storage_manager, node_id, deployment):
    try:
        return get_node(deployment.id, node_id)
    except manager_exceptions.NotFoundError:
        node = Node(
            id=node_id,
            type='',
            number_of_instances=1,
            planned_number_of_instances=1,
            deploy_number_of_instances=1,
            min_number_of_instances=1,
            max_number_of_instances=1
        )
        node.deployment = deployment
        return storage_manager.put(node)


def upload_mock_cloudify_license(storage_manager):
    license = License(
        customer_id='mock_customer',
        expiration_date=datetime.now(),
        license_edition='Spire',
        cloudify_version='4.6',
        capabilities='mock-capabilities',

    )
    storage_manager.put(license)

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

from cloudify_rest_client.client import HTTPClient
from cloudify_rest_client.executions import Execution
from manager_rest.storage import get_storage_manager, models

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
                   versioned_url=True):
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
            stream=stream)

    def _do_request(self, requests_method, request_url, body, params, headers,
                    expected_status_code, stream, verify):
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
            raise NotImplemented()

        if response.status_code != expected_status_code:
            response.content = response.data
            response.json = lambda: json.loads(response.data)
            self._raise_client_error(response, request_url)

        if stream:
            return MockStreamedResponse(response, self._file_server)
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
    return Execution.TERMINATED


class MockCeleryClient(object):

    def execute_task(self, task_queue, task_id=None, kwargs=None):
        sm = get_storage_manager()
        execution = sm.get(models.Execution, task_id)
        execution.status = task_state()
        execution.error = ''
        sm.update(execution)
        return MockAsyncResult(task_id)

    def get_task_status(self, task_id):
        return 'SUCCESS'

    def get_failed_task_error(self, task_id):
        return RuntimeError('mock error')

    # this is just to be on par with the CeleryClient API
    def close(self):
        pass


class MockAsyncResult(object):

    def __init__(self, task_id):
        self.id = task_id

    def get(self, timeout=300, propagate=True):
        return None

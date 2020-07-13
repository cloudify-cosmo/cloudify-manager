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


def query(root_uri, query_string, auth=None, ca_path=None, timeout=None):
    query_uri = '{0}api/v1/query'.format(root_uri)
    params = {'query': query_string}
    try:
        r = requests.get(query_uri,
                         params=params,
                         auth=auth,
                         verify=ca_path if ca_path else True,
                         timeout=timeout)
    except requests.exceptions.ConnectionError:
        return []
    return _format_prometheus_response(r) or []


def _format_prometheus_response(response):
    if response.status_code == requests.codes.ok and 'data' in response.json():
        response_data = response.json()['data']
        if 'result' in response_data and 'resultType' in response_data:
            return response_data['result']
    return None

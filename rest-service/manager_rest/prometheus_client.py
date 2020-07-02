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


PROMETHEUS_ROOT_URI = 'http://localhost:9090/monitoring/'


def alerts():
    """
    Get list of pending or firing alerts from Prometheus.
    Returns a list of alerts in case of successful communication, None
    otherwise.
    """
    alerts_uri = '{0}api/v1/alerts'.format(PROMETHEUS_ROOT_URI)
    r = requests.get(alerts_uri)
    if r.status_code == requests.codes.ok and 'data' in r.json():
        return r.json()['data']['alerts']
    return None

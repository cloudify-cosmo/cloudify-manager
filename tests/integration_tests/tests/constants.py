#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

MANAGER_CONFIG = {
    'workflow': {
        'task_retries': 0,
        'task_retry_interval': 0,
        'subgraph_retries': 0
    },
}
PROVIDER_NAME = 'integration_tests'

USER_ROLE = 'default'
ADMIN_ROLE = 'sys_admin'
USER_IN_TENANT_ROLE = 'user'

SCHEDULED_TIME_FORMAT = '{year}{month}{day}{hour}{minute}+0000'
MANAGER_PYTHON = '/opt/manager/env/bin/python'

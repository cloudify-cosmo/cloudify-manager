########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import tempfile

FILE_SERVER_PORT = 53229
MANAGER_REST_PORT = 8100
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'

FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER = 'uploaded-blueprints'
FILE_SERVER_RESOURCES_URI = '/resources'
RABBITMQ_POLLING_KEY = 'RABBITMQ_POLLING'
RABBITMQ_POLLING_ENABLED = \
    RABBITMQ_POLLING_KEY not in \
    os.environ or os.environ[RABBITMQ_POLLING_KEY].lower() != 'false'
RABBITMQ_VERBOSE_MESSAGES_KEY = 'RABBITMQ_VERBOSE_MESSAGES'
RABBITMQ_VERBOSE_MESSAGES_ENABLED = os.environ.get(
    RABBITMQ_VERBOSE_MESSAGES_KEY, 'false').lower() == 'true'

STORAGE_INDEX_NAME = 'cloudify_storage'

PLUGIN_STORAGE_PATHS = {
    'worker_installer': '{0}/agent-installer-data.json',
    'cloudmock': '{0}/cloudmock-data.json'
}

WORKERS_ENV_DIR_SUFFIX = 'workers'

TOP_LEVEL_DIR = os.path.join(
    tempfile.gettempdir(),
    'cloudify-integration-tests'
)

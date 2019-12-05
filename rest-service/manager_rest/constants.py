#########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
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

CONVENTION_APPLICATION_BLUEPRINT_FILE = 'blueprint.yaml'

SUPPORTED_ARCHIVE_TYPES = ['zip', 'tar', 'tar.gz', 'tar.bz2']

MAINTENANCE_MODE_STATUS_FILE = 'status.json'
MAINTENANCE_MODE_ACTIVATING = 'activating'
MAINTENANCE_MODE_ACTIVATED = 'activated'
MAINTENANCE_MODE_DEACTIVATED = 'deactivated'
MAINTENANCE_MODE_ACTIVE_ERROR_CODE = 'maintenance_mode_active'
MAINTENANCE_MODE_ACTIVATING_ERROR_CODE = 'entering_maintenance_mode'

PROVIDER_CONTEXT_ID = 'CONTEXT'

CLOUDIFY_TENANT_HEADER = 'Tenant'
CURRENT_TENANT_CONFIG = 'current_tenant'
DEFAULT_TENANT_NAME = 'default_tenant'

DEFAULT_SYSTEM_ROLE = 'default'
DEFAULT_TENANT_ROLE = 'user'

BOOTSTRAP_ADMIN_ID = 0
DEFAULT_TENANT_ID = 0

REST_SERVICE_NAME = 'cloudify-restservice'

FILE_SERVER_RESOURCES_FOLDER = '/resources'
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'
FILE_SERVER_DEPLOYMENTS_FOLDER = 'deployments'
FILE_SERVER_GLOBAL_RESOURCES_FOLDER = 'global-resources'
FILE_SERVER_TENANT_RESOURCES_FOLDER = 'tenant-resources'
FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER = 'uploaded-blueprints'
FILE_SERVER_SNAPSHOTS_FOLDER = 'snapshots'
FILE_SERVER_PLUGINS_FOLDER = 'plugins'
FILE_SERVER_AUTHENTICATORS_FOLDER = 'authenticators'
TEMP_SNAPSHOT_FOLDER_SUFFIX = 'snapshot-data'


SECURITY_FILE_LOCATION = '/opt/manager/rest-security.conf'

LOCAL_ADDRESS = '127.0.0.1'
ALLOWED_ENDPOINTS = ['status', 'version', 'license', 'maintenance']
ALLOWED_MAINTENANCE_ENDPOINTS = ALLOWED_ENDPOINTS + ['snapshots',
                                                     'snapshot-status',
                                                     'cluster-status']
ALLOWED_LICENSE_ENDPOINTS = ALLOWED_ENDPOINTS + [
    'tokens', 'config', 'cluster', 'tenants', 'brokers', 'managers'
]
CLOUDIFY_AUTH_HEADER = 'Authorization'
CLOUDIFY_AUTH_TOKEN_HEADER = 'Authentication-Token'
BASIC_AUTH_PREFIX = 'Basic '
MODELS_TO_PERMISSIONS = {
    'NodeInstance': 'node_instance',
    'TasksGraph': 'operations'
}
FORBIDDEN_METHODS = ['POST', 'PATCH', 'PUT']
SANITY_MODE_FILE_PATH = '/opt/manager/sanity_mode'

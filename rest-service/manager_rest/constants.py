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

BOOTSTRAP_ADMIN_ID = 0
DEFAULT_TENANT_ID = 0

ADMIN_ROLE = 'admin'
USER_ROLE = 'user'

ALL_ROLES = [ADMIN_ROLE, USER_ROLE]

REST_SERVICE_NAME = 'cloudify-restservice'

FILE_SERVER_RESOURCES_FOLDER = '/resources'
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'
FILE_SERVER_DEPLOYMENTS_FOLDER = 'deployments'
FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER = 'uploaded-blueprints'
FILE_SERVER_SNAPSHOTS_FOLDER = 'snapshots'
FILE_SERVER_PLUGINS_FOLDER = 'plugins'

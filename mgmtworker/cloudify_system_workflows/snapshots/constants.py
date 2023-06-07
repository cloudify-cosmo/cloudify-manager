########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from os.path import join
from cloudify.utils import ManagerVersion

HASH_SALT_FILENAME = 'hash_salt.json'
ADMIN_DUMP_FILE = 'admin_account.json'
LICENSE_DUMP_FILE = 'license.json'
METADATA_FILENAME = 'metadata.json'
M_VERSION = 'snapshot_version'
M_SCHEMA_REVISION = 'schema_revision'
M_STAGE_SCHEMA_REVISION = 'stage_schema_revision'
M_COMPOSER_SCHEMA_REVISION = 'composer_schema_revision'
M_HAS_CLOUDIFY_EVENTS = 'has_cloudify_events'
M_EXECUTION_ID = 'execution_id'
ARCHIVE_CERT_DIR = 'ssl'
CERT_DIR = '/etc/cloudify/ssl'
INTERNAL_CA_CERT_FILENAME = 'cloudify_internal_ca_cert.pem'
INTERNAL_CA_KEY_FILENAME = 'cloudify_internal_ca_key.pem'
INTERNAL_CERT_FILENAME = 'cloudify_internal_cert.pem'
INTERNAL_KEY_FILENAME = 'cloudify_internal_key.pem'
BROKER_DEFAULT_VHOST = '/'
DEFAULT_TENANT_NAME = 'default_tenant'
SECRET_STORE_AGENT_KEY_PREFIX = 'cfyagent_key__'
STAGE_BASE_FOLDER = '/opt/cloudify-stage'
STAGE_WIDGETS_FOLDER = 'dist/widgets'
STAGE_TEMPLATES_FOLDER = 'dist/templates'
STAGE_USERDATA_FOLDER = 'dist/userData'
STAGE_USER = 'stage_user'
STAGE_APP = 'stage'
# created during bootstrap
STAGE_RESTORE_SCRIPT = '/opt/cloudify/stage/restore-snapshot.py'
MANAGER_PYTHON = '/opt/manager/env/bin/python'
ADMIN_TOKEN_SCRIPT = '/opt/cloudify/mgmtworker/create-admin-token.py'
ALLOW_DB_CLIENT_CERTS_SCRIPT = (
    '/opt/cloudify/mgmtworker/allow-snapshot-ssl-client-cert-access'
)
DENY_DB_CLIENT_CERTS_SCRIPT = (
    '/opt/cloudify/mgmtworker/deny-snapshot-ssl-client-cert-access'
)
COMPOSER_BASE_FOLDER = '/opt/cloudify-composer'
COMPOSER_BLUEPRINTS_FOLDER = 'backend/dev'
COMPOSER_USER = 'composer_user'
COMPOSER_APP = 'composer'
SECURITY_FILENAME = 'rest-security.conf'
SECURITY_FILE_LOCATION = join('/opt/manager/', SECURITY_FILENAME)
REST_AUTHORIZATION_CONFIG_PATH = '/opt/manager/authorization.conf'


V_4_0_0 = ManagerVersion('4.0.0')
V_4_1_0 = ManagerVersion('4.1.0')
V_4_2_0 = ManagerVersion('4.2.0')
V_4_3_0 = ManagerVersion('4.3.0')
V_4_4_0 = ManagerVersion('4.4.0')
V_4_5_5 = ManagerVersion('4.5.5')
V_4_6_0 = ManagerVersion('4.6.0')
V_5_0_5 = ManagerVersion('5.0.5')
V_5_1_0 = ManagerVersion('5.1.0')
V_5_2_0 = ManagerVersion('5.2.0')
V_5_3_0 = ManagerVersion('5.3.0')
V_6_0_0 = ManagerVersion('6.0.0')
V_7_0_0 = ManagerVersion('7.0.0')
V_7_1_0 = ManagerVersion('7.1.0')


DUMP_TYPE_IDS = {
    'agents': 'agent_ids',
    'blueprints': 'blueprint_ids',
    'deployment_updates': 'deployment_update_ids',
    'deployments': 'deployment_ids',
    'events': 'event_storage_ids',
    'execution_schedules': 'execution_schedule_ids',
    'execution_groups': 'execution_group_ids',
    'executions': 'execution_ids',
    'blueprints_filters': 'filter_ids',
    'deployments_filters': 'filter_ids',
    'inter_deployment_dependencies': 'inter_deployment_dependency_ids',
    'node_instances': 'node_instance_ids',
    'nodes': 'node_ids',
    'tasks_graphs': 'tasks_graph_ids',
    'plugins': 'plugin_ids',
    'plugins_updates': 'plugins_update_ids',
    'secrets_providers': 'secrets_provider_ids',
    'sites': 'sites_ids',
}


class VisibilityState(object):
    PRIVATE = 'private'
    TENANT = 'tenant'
    GLOBAL = 'global'

    STATES = [PRIVATE, TENANT, GLOBAL]

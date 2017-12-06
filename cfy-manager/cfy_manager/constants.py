#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

from os.path import join, dirname

BASE_DIR = dirname(__file__)
COMPONENTS_DIR = join(BASE_DIR, 'components')

CLOUDIFY_INSTALL_DIR = '/opt/cloudify'
USER_CONFIG_PATH = join(CLOUDIFY_INSTALL_DIR, 'config.yaml')
# For defaults, use the version supplied in the package
DEFAULT_CONFIG_PATH = join(dirname(BASE_DIR), 'config.yaml')

CLOUDIFY_USER = 'cfyuser'
CLOUDIFY_GROUP = 'cfyuser'
CLOUDIFY_HOME_DIR = '/etc/cloudify'
SUDOERS_INCLUDE_DIR = '/etc/sudoers.d'
CLOUDIFY_SUDOERS_FILE = join(SUDOERS_INCLUDE_DIR, CLOUDIFY_USER)

BASE_RESOURCES_PATH = '/opt/cloudify'
CLOUDIFY_SOURCES_PATH = join(BASE_RESOURCES_PATH, 'sources')
MANAGER_RESOURCES_HOME = '/opt/manager/resources'
AGENT_ARCHIVES_PATH = '{0}/packages/agents'.format(MANAGER_RESOURCES_HOME)

BASE_LOG_DIR = '/var/log/cloudify'

INTERNAL_REST_PORT = 53333

SSL_CERTS_TARGET_DIR = join(CLOUDIFY_HOME_DIR, 'ssl')

INTERNAL_CERT_FILENAME = 'cloudify_internal_cert.pem'
INTERNAL_KEY_FILENAME = 'cloudify_internal_key.pem'
CA_CERT_FILENAME = 'cloudify_internal_ca_cert.pem'
CA_KEY_FILENAME = 'cloudify_internal_ca_key.pem'
INTERNAL_PKCS12_FILENAME = 'cloudify_internal.p12'
EXTERNAL_CERT_FILENAME = 'cloudify_external_cert.pem'
EXTERNAL_KEY_FILENAME = 'cloudify_external_key.pem'

INTERNAL_CERT_PATH = join(SSL_CERTS_TARGET_DIR, INTERNAL_CERT_FILENAME)
INTERNAL_KEY_PATH = join(SSL_CERTS_TARGET_DIR, INTERNAL_KEY_FILENAME)
CA_CERT_PATH = join(SSL_CERTS_TARGET_DIR, CA_CERT_FILENAME)
CA_KEY_PATH = join(SSL_CERTS_TARGET_DIR, CA_KEY_FILENAME)
EXTERNAL_CERT_PATH = join(SSL_CERTS_TARGET_DIR, EXTERNAL_CERT_FILENAME)
EXTERNAL_KEY_PATH = join(SSL_CERTS_TARGET_DIR, EXTERNAL_KEY_FILENAME)
CERT_METADATA_FILE_PATH = join(SSL_CERTS_TARGET_DIR, 'certificate_metadata')

CFY_EXEC_TEMPDIR_ENVVAR = 'CFY_EXEC_TEMP'

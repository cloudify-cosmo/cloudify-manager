########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# User configured environment variables
#######################################
# if your test fetches hello world or some other repo, configure this env var
# to your liking if you wish to use a branch different than master
BRANCH_NAME_CORE = 'BRANCH_NAME_CORE'

# Internal framework environment variables
##########################################
DOCL_CONTAINER_IP = 'DOCL_CONTAINER_IP'
CLOUDIFY_REST_PORT = 'CLOUDIFY_REST_PORT'

PLUGIN_STORAGE_DIR = '/opt/integration-plugin-storage'
DOCKER_COMPUTE_DIR = '/etc/cloudify/dockercompute'

CONFIG_FILE_LOCATION = '/opt/manager/cloudify-rest.conf'
AUTHORIZATION_FILE_LOCATION = '/opt/manager/authorization.conf'

CLOUDIFY_USER = 'cfyuser'
ADMIN_TOKEN_SCRIPT = '/opt/cloudify/mgmtworker/create-admin-token.py'

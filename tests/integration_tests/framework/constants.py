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
ADMIN_TOKEN_SCRIPT = '/opt/cloudify/mgmtworker/create-admin-token.py'

INSERT_MOCK_LICENSE_QUERY = "INSERT INTO licenses(customer_id, " \
                            "expiration_date, license_edition, trial," \
                            " cloudify_version, capabilities, signature)" \
                            " VALUES('MockCustomer', '2050-01-01', 'Spire'," \
                            " false, '4.6', '{mock}', 'mock_signature');"

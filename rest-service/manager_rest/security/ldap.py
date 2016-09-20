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

from manager_rest import config

# TODO: Change to regular import after ldapy is part of the build
try:
    from ldappy import Ldappy
except ImportError:
    Ldappy = None


def get_ldappy():
    """Attempt to create an Ldappy connection object using config params
    """
    if not Ldappy:
        return None

    # If the configuration wasn't set explicitly, don't use LDAP
    if not config.instance.ldap_server:
        return None

    # TODO: This is here until the new version of Ldappy takes care of it
    domain = config.instance.ldap_domain
    domain_component = 'dc=' + ',dc='.join(domain.split('.'))

    ldap_config = {
        'ldap_server': config.instance.ldap_server,
        'username': config.instance.ldap_username,
        'password': config.instance.ldap_password,
        'domain': config.instance.ldap_domain,
        'domain_component': domain_component,
        'active_directory': config.instance.ldap_is_active_directory,
        'organization_id': config.instance.ldap_dn_extra
    }

    return Ldappy(ldap_config)

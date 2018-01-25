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
#

import pkg_resources
import subprocess
from flask_restful_swagger import swagger

from manager_rest.rest import responses
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
)


def get_version():
    return pkg_resources.get_distribution('cloudify-rest-service').version


def get_version_data():
    version = get_version()
    try:
        pckg = pkg_resources.get_distribution('cloudify-premium')
        edition = 'premium'
        version = pckg.version
    except pkg_resources.DistributionNotFound:
        edition = 'community'
        try:
            rpm_info = subprocess.check_output(['rpm', '-q', 'cloudify'])
            version = rpm_info.split('-')[1]
        except subprocess.CalledProcessError:
            pass
        except OSError:
            pass

    return {
        'version': version,
        'edition': edition
    }


class Version(SecuredResource):

    @swagger.operation(
        responseClass=responses.Version,
        nickname="version",
        notes="Returns version information for this rest service"
    )
    @exceptions_handled
    @authorize('version_get')
    @marshal_with(responses.Version)
    def get(self, **kwargs):
        """
        Get version information
        """
        return get_version_data()

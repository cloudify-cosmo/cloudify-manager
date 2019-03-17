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


from flask import request

from manager_rest.rest import responses_v3
from manager_rest.security.authorization import authorize
from manager_rest.security import MissingPremiumFeatureResource
from manager_rest.rest.rest_decorators import (
    exceptions_handled,
    marshal_with,
    paginate
)
try:
    from cloudify_premium import SecuredLicenseResource
except ImportError:
    SecuredLicenseResource = MissingPremiumFeatureResource


class License(SecuredLicenseResource):
    @exceptions_handled
    @marshal_with(responses_v3.License)
    @authorize('license_upload')
    def put(self, license_handler):
        """
        Upload a new Cloudify license to the Manager.
        """

        full_license = request.data
        return license_handler.upload_license(full_license)

    @exceptions_handled
    @marshal_with(responses_v3.License)
    @paginate
    @authorize('license_list')
    def get(self, license_handler, pagination=None):
        """
        List registered Cloudfiy licenses.
        """
        return license_handler.list_license()

from flask import request

from manager_rest.rest import responses_v3
from manager_rest.security.authorization import authorize
from manager_rest.security import (
    MissingPremiumFeatureResource,
    SecuredResource,
)
from manager_rest.rest.rest_decorators import (
    marshal_with,
    paginate
)
try:
    from cloudify_premium.license.secured_license_resource import (
        SecuredLicenseResource)
except ImportError:
    SecuredLicenseResource = MissingPremiumFeatureResource


class License(SecuredLicenseResource):
    @marshal_with(responses_v3.License)
    @authorize('license_upload')
    def put(self, license_handler):
        """
        Upload a new Cloudify license to the Manager.
        """

        full_license = request.data
        return license_handler.upload_license(full_license)

    @marshal_with(responses_v3.License)
    @paginate
    @authorize('license_list')
    def get(self, license_handler, pagination=None):
        """
        List registered Cloudfiy licenses.
        """
        return license_handler.list_license()


class LicenseCheck(SecuredResource):
    def get(self):
        return "OK", 200

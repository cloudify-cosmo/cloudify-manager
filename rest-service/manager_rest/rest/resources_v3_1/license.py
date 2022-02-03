from flask import request

from cloudify._compat import text_type
from manager_rest.rest import responses_v3
from manager_rest.security.authorization import authorize
from manager_rest.security import (
    MissingPremiumFeatureResource,
    SecuredResource,
    premium_only
)
from manager_rest.manager_exceptions import ConflictError
from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import get_json_and_verify_params
from manager_rest.rest.rest_decorators import (
    marshal_with,
    paginate
)
try:
    from cloudify_premium.license.secured_license_resource import (
        SecuredLicenseResource)
    _PREMIUM = True
except ImportError:
    SecuredLicenseResource = MissingPremiumFeatureResource
    _PREMIUM = False


class LicensePremium(SecuredLicenseResource):
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


class LicenseCommunity(SecuredResource):
    @marshal_with(responses_v3.License)
    @authorize('license_upload')
    def post(self):
        """
        Store the Customer ID received from Hubspot in the Manager.
        """
        request_dict = get_json_and_verify_params({
            'customer_id': {'type': text_type},
        })
        sm = get_storage_manager()
        licenses = sm.list(models.License)
        customer_id = str(licenses[0].customer_id) if licenses else None
        if customer_id:
            raise ConflictError(
                'A Customer ID already exists for this manager: '
                '{}'.format(customer_id))
        return sm.put(models.License(customer_id=request_dict['customer_id']))

    @premium_only
    def put(self):
        raise NotImplementedError('Premium implementation only')

    @premium_only
    def get(self):
        raise NotImplementedError('Premium implementation only')


License = LicensePremium if _PREMIUM else LicenseCommunity


class LicenseCheck(SecuredResource):
    def get(self):
        return "OK", 200

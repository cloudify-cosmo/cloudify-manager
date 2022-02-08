from requests import post
from flask import current_app
from json import JSONDecodeError

from cloudify._compat import text_type
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest import premium_enabled, manager_exceptions
from manager_rest.rest.rest_utils import get_json_and_verify_params

CREATE_CONTACT_URL = "https://api.cloudify.co/cloudifyCommunityCreateContact"


class CommunityContacts(SecuredResource):
    @authorize('community_contact_create')
    def post(self, **kwargs):
        if premium_enabled:
            raise manager_exceptions.CommunityOnly()
        request_dict = get_json_and_verify_params({
            'first_name': {'type': text_type},
            'last_name': {'type': text_type},
            'email': {'type': text_type},
            'phone': {'type': text_type},
            'is_eula': {'type': bool},
            'is_send_services_details': {'optional': True, 'type': bool}
        })
        if not request_dict['is_eula']:
            raise manager_exceptions.BadParametersError(
                "EULA must be confirmed by user")
        r = post(CREATE_CONTACT_URL, json={
            "firstname": request_dict['first_name'],
            "lastname": request_dict['last_name'],
            "email": request_dict['email'],
            "phone": request_dict['phone'],
            "send_services_details":
                request_dict.get('is_send_services_details')
        })
        generic_error_msg = 'There was a problem while submiting the form, ' \
                            'please try later'
        error_log_msg = 'Error creating contact "%s" - %s: %s'
        if not r.ok:
            current_app.logger.error(error_log_msg,
                                     request_dict['email'],
                                     r.status_code,
                                     r.text)
            raise manager_exceptions.UnknownAction(generic_error_msg)
        try:
            r_json = r.json()
        except JSONDecodeError:
            current_app.logger.error(error_log_msg,
                                     request_dict['email'],
                                     500,
                                     "Could not decode response JSON")
            raise manager_exceptions.UnknownAction(generic_error_msg)

        r_status = r_json['status']
        if r_status == 200:
            return {'customer_id': 'COM-{}-{}'.format(r_json['company_name'],
                                                      r_json['contact_id'])}
        elif r_status == 409:
            current_app.logger.error(error_log_msg,
                                     request_dict['email'],
                                     r_status,
                                     r_json['message'])
            raise manager_exceptions.ConflictError(
                'There was a conflict while submiting your details')
        else:
            current_app.logger.error(error_log_msg,
                                     request_dict['email'],
                                     r_status,
                                     r_json['message'])
            raise manager_exceptions.UnknownAction(generic_error_msg)

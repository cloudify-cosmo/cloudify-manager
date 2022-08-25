import pydantic
from typing import Optional

from requests import post
from flask import current_app, request
from json import JSONDecodeError

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest import premium_enabled, manager_exceptions


CREATE_CONTACT_URL = "https://api.cloudify.co/cloudifyCommunityCreateContact"


class _CreateContactArgs(pydantic.BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    is_eula: bool


class CommunityContacts(SecuredResource):
    @authorize('community_contact_create')
    def post(self, **kwargs):
        if premium_enabled:
            raise manager_exceptions.CommunityOnly()
        request_dict = _CreateContactArgs.parse_obj(request.json).dict()
        if not request_dict['is_eula']:
            raise manager_exceptions.BadParametersError(
                "EULA must be confirmed by user")
        r = post(CREATE_CONTACT_URL, json={
            "firstname": request_dict['first_name'],
            "lastname": request_dict['last_name'],
            "email": request_dict['email'],
            "phone": request_dict['phone'],
            "is_eula": request_dict['is_eula'],
        })
        generic_error_msg = 'There was a problem while submitting the form, ' \
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
        else:
            current_app.logger.error(error_log_msg,
                                     request_dict['email'],
                                     r_status,
                                     r_json['message'])
            raise manager_exceptions.UnknownAction(generic_error_msg)

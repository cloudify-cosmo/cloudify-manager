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

from .... import rest_utils, rest_decorators
from . import base


class ARIAService(base.BaseARIAEndpoints):
    @rest_decorators.exceptions_handled
    def get(self, service_id, **kwargs):
        """
        Get Service by id
        """
        return self.model.service.get(service_id).to_dict()

    def delete(self, service_id, force=False, **kwargs):
        """
        delete Service by id
        """
        service = self.model.service.get(service_id)
        self.core.delete_service(service_id, force)
        return service, 200


class ARIAServices(base.BaseARIAEndpoints):
    @rest_decorators.create_filters()
    def get(self,
            _include=None,
            filters=None, pagination=None, sort=None,
            **kwargs):
        """
        Get a Service list
        """
        return self._respond_list(
            self.model.service.list(
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                **kwargs
            )
        )

    @rest_decorators.exceptions_handled
    def put(self, **kwargs):
        """
        create a Service template
        """
        request_dict = rest_utils.get_json_and_verify_params(
            dict(
                service_template_id={},
                service_name={'optional': True, 'type': basestring},
                inputs={'optional': True, 'type': dict}
            )
        )
        service = self.core.create_service(
            request_dict['service_template_id'],
            inputs=request_dict.get('inputs', {}),
            service_name=request_dict['service_name'])
        return service.to_dict(
            service.fields() - {'created_at', 'updated_at'}), \
            201

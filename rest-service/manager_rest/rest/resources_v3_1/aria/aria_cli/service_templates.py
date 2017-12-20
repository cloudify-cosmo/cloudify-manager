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
import json

from ..... import upload_manager
from .... import rest_decorators
from .. import base


class ARIAServiceTemplate(base.BaseARIAEndpoints):

    def put(self, service_template_id, **kwargs):
        """
        Upload a service template
        """
        service_template_manager = \
            upload_manager.UploadARIAServiceTemplateManager(self.core)
        service_template, status_code = \
            service_template_manager.receive_uploaded_data(service_template_id)

        # This should definitly change once we use the flask-sqlalcehmy
        # integration
        raw_service_template_as_dict = service_template.to_dict()
        service_template_as_dict = {}
        for key, value in raw_service_template_as_dict.items():
            try:
                json.dumps(value)
                service_template_as_dict[key] = value
            except TypeError:
                # TypeError is raised when json.dumps tried to jump an
                # unpicklable entity
                pass

        return service_template_as_dict, status_code

    @rest_decorators.exceptions_handled
    def get(self, service_template_id, **kwargs):
        """
        Get ServiceTemplate by id
        """
        return self.model.service_template.get(service_template_id).to_dict()

    def delete(self, service_template_id, **kwargs):
        """
        delete ServiceTemplate by id
        """
        service_template = self.model.service_template.get(service_template_id)
        self.core.delete_service_template(service_template_id)
        return service_template, 200


class ARIAServiceTemplates(base.BaseARIAEndpoints):
    @rest_decorators.create_filters()
    def get(self, _include=None, filters=None, sort=None, **kwargs):
        """
        Get a ServiceTemplates list
        """
        return self._respond_list(
            self.model.service_template.list(
                include=_include,
                filters=dict((k, v[0]) for k, v in filters.items()),
                sort=sort,
                **kwargs
            )
        )

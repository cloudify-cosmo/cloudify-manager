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

import os


def get_service_template(
        blueprint_file_name,
        service_template_dir='mock_service_templates'
):
    from .... import test
    source_dir = os.path.join(
        os.path.dirname(os.path.abspath(test.__file__)),
        service_template_dir
    )
    return os.path.join(source_dir, blueprint_file_name)


def upload_service_template(client, template_source, template_name):
    return client.aria_service_templates.upload(
        service_template_path=template_source,
        service_template_id=template_name,
    )


def create_service_from_service_template(
        client, service_name, service_template_id
):
    return client.aria_services.create(service_template_id, service_name)


def create_service(
        client,
        app_yaml,
        service_template_path,
        service_name=None
):

    service_name = (service_name or
                    '{name}-service'.format(name=service_template_path))
    upload_service_template(
        client, get_service_template(app_yaml), service_template_path
    )
    service_template = client.aria_service_templates.list(
        name=service_template_path
    )[0]

    create_service_from_service_template(
        client, service_name, service_template.id)

#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from flask_restful_swagger import swagger


"""
This method is based on swagger's
:func:'flask_restful_swagger.swagger.docs.add_resource' and modifies it to
support multiple API versions. These changes were made:

1. This method should be called directly for every API resource created.
AVOID calling :func:'flask_restful_swagger.swagger.docs', or it will override
Flask-Restful's 'add_resource' with swagger's implementation!
    e.g. add_swagger_resource(api, api_version, resource, '/v1/my_endpoint')

2. This method only registers swagger APIs. A separate call to Flask-Restful's
'add_resource' is required in order to register the "real" API resource.
        e.g: api.add_resource(resource, endpoint_url)

3. swagger's endpoint_paths contain the api version now, to support multiple
versions of the same resource on the same API

"""


def add_swagger_resource(api, api_version, resource, resource_path):
    endpoint = swagger.swagger_endpoint(resource, resource_path)
    # Add a .help.json help url
    swagger_path = swagger.extract_swagger_path(resource_path)
    endpoint_path = "{0}_{1}_help_json".format(api_version, resource.__name__)
    api.add_resource(endpoint, "%s.help.json" % swagger_path,
                     endpoint=endpoint_path)
    # Add a .help.html help url
    endpoint_path = "{0}_{1}_help_html".format(api_version, resource.__name__)
    api.add_resource(endpoint, "%s.help.html" % swagger_path,
                     endpoint=endpoint_path)
    swagger.register_once(
        add_resource_func=api.add_resource, apiVersion=api_version,
        swaggerVersion='1.2',
        basePath='http://localhost:8100',
        resourcePath='/', produces=["application/json"],
        endpoint='/api/spec')

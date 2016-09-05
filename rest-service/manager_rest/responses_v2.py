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

from flask.ext.restful import fields
from flask_restful_swagger import swagger

from manager_rest.responses import (BlueprintState as BlueprintStateV1,  # NOQA
                                    Execution,
                                    Deployment,
                                    DeploymentModification,
                                    Node,
                                    NodeInstance,
                                    ProviderContext)


@swagger.model
class BlueprintState(BlueprintStateV1):

    resource_fields = dict(BlueprintStateV1.resource_fields.items() + {
        'description': fields.String,
        'main_file_name': fields.String
    }.items())

    def __init__(self, **kwargs):
        super(BlueprintState, self).__init__(**kwargs)
        self.description = kwargs.get('description')
        self.main_file_name = kwargs.get('main_file_name')


@swagger.model
class Plugin(object):
    resource_fields = {
        'id': fields.String,
        'package_name': fields.String,
        'archive_name': fields.String,
        'package_source': fields.String,
        'package_version': fields.String,
        'supported_platform': fields.String,
        'distribution': fields.String,
        'distribution_version': fields.String,
        'distribution_release': fields.String,
        'wheels': fields.Raw,
        'excluded_wheels': fields.Raw,
        'supported_py_versions': fields.Raw,
        'uploaded_at': fields.String}

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.package_name = kwargs.get('package_name')
        self.archive_name = kwargs.get('archive_name')
        self.package_source = kwargs.get('package_source')
        self.package_version = kwargs.get('package_version')
        self.supported_platform = kwargs.get('supported_platform')
        self.distribution = kwargs.get('distribution')
        self.distribution_version = kwargs.get('distribution_version')
        self.distribution_release = kwargs.get('distribution_release')
        self.wheels = kwargs.get('wheels')
        self.excluded_wheels = kwargs.get('excluded_wheels')
        self.supported_py_versions = kwargs.get('supported_py_versions')
        self.uploaded_at = kwargs.get('uploaded_at')


@swagger.model
class Snapshot(object):

    resource_fields = {
        'id': fields.String,
        'created_at': fields.String,
        'status': fields.String,
        'error': fields.String
    }

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.created_at = kwargs.get('created_at')
        self.status = kwargs.get('status')
        self.error = kwargs.get('error')


@swagger.model
class ListResponse(object):
    resource_fields = {
        'metadata': fields.Raw,
        'items': fields.List(fields.Raw)}

    def __init__(self, **kwargs):
        self.metadata = kwargs.get('metadata')
        self.items = kwargs.get('items')

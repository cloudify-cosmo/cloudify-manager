#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'ran'


INTERNAL_SERVER_ERROR_CODE = 'internal_server_error'

BAD_PARAMETERS_ERROR_CODE = 'bad_parameters_error'
INVALID_BLUEPRINT_ERROR_CODE = 'invalid_blueprint_error'
EXISTING_RUNNING_EXECUTION_ERROR_CODE = 'existing_running_execution_error'
UNSUPPORTED_CONTENT_TYPE_ERROR_CODE = 'unsupported_content_type_error'
NONEXISTENT_WORKFLOW_ERROR_CODE = 'bad_content_type_error'
CONFLICT_ERROR_CODE = 'conflict_error'
NOT_FOUND_ERROR_CODE = 'not_found_error'
DEPENDENT_EXISTS_ERROR_CODE = 'dependent_exists_error'
DEPLOYMENT_WORKERS_NOT_YET_INSTALLED_ERROR_CODE = \
    'deployment_workers_not_yet_installed_error'


class ManagerException(Exception):
    def __init__(self, http_code, error_code, *args, **kwargs):
        super(ManagerException, self).__init__(*args, **kwargs)
        self.http_code = http_code
        self.error_code = error_code


class ConflictError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(ConflictError, self).__init__(
            409, CONFLICT_ERROR_CODE, *args, **kwargs)


class NotFoundError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(NotFoundError, self).__init__(
            404, NOT_FOUND_ERROR_CODE, *args, **kwargs)


class DependentExistsError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(DependentExistsError, self).__init__(
            400, DEPENDENT_EXISTS_ERROR_CODE, *args, **kwargs)


class NonexistentWorkflowError(ManagerException):

    def __init__(self, *args, **kwargs):
        super(NonexistentWorkflowError, self).__init__(
            400, NONEXISTENT_WORKFLOW_ERROR_CODE, *args, **kwargs)


class UnsupportedContentTypeError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(UnsupportedContentTypeError, self).__init__(
            415, UNSUPPORTED_CONTENT_TYPE_ERROR_CODE, *args, **kwargs)


class BadParametersError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(BadParametersError, self).__init__(
            400, BAD_PARAMETERS_ERROR_CODE, *args, **kwargs)


class InvalidBlueprintError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(InvalidBlueprintError, self).__init__(
            400, INVALID_BLUEPRINT_ERROR_CODE, *args, **kwargs)


class ExistingRunningExecutionError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(ExistingRunningExecutionError, self).__init__(
            400, EXISTING_RUNNING_EXECUTION_ERROR_CODE, *args, **kwargs)


class DeploymentWorkersNotYetInstalledError(ManagerException):
    def __init__(self, *args, **kwargs):
        super(DeploymentWorkersNotYetInstalledError, self).__init__(
            400, DEPLOYMENT_WORKERS_NOT_YET_INSTALLED_ERROR_CODE, *args,
            **kwargs)

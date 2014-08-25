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


INTERNAL_SERVER_ERROR_CODE = 'internal_server_error'


class ManagerException(Exception):
    def __init__(self, http_code, error_code, *args, **kwargs):
        super(ManagerException, self).__init__(*args, **kwargs)
        self.http_code = http_code
        self.error_code = error_code


class ConflictError(ManagerException):
    CONFLICT_ERROR_CODE = 'conflict_error'

    def __init__(self, *args, **kwargs):
        super(ConflictError, self).__init__(
            409, ConflictError.CONFLICT_ERROR_CODE, *args, **kwargs)


class NotFoundError(ManagerException):
    NOT_FOUND_ERROR_CODE = 'not_found_error'

    def __init__(self, *args, **kwargs):
        super(NotFoundError, self).__init__(
            404, NotFoundError.NOT_FOUND_ERROR_CODE, *args, **kwargs)


class DependentExistsError(ManagerException):
    DEPENDENT_EXISTS_ERROR_CODE = 'dependent_exists_error'

    def __init__(self, *args, **kwargs):
        super(DependentExistsError, self).__init__(
            400, DependentExistsError.DEPENDENT_EXISTS_ERROR_CODE,
            *args, **kwargs)


class NonexistentWorkflowError(ManagerException):
    NONEXISTENT_WORKFLOW_ERROR_CODE = 'nonexistent_workflow_error'

    def __init__(self, *args, **kwargs):
        super(NonexistentWorkflowError, self).__init__(
            400,
            NonexistentWorkflowError.NONEXISTENT_WORKFLOW_ERROR_CODE,
            *args,
            **kwargs)


class UnsupportedContentTypeError(ManagerException):
    UNSUPPORTED_CONTENT_TYPE_ERROR_CODE = 'unsupported_content_type_error'

    def __init__(self, *args, **kwargs):
        super(UnsupportedContentTypeError, self).__init__(
            415,
            UnsupportedContentTypeError.UNSUPPORTED_CONTENT_TYPE_ERROR_CODE,
            *args,
            **kwargs)


class BadParametersError(ManagerException):
    BAD_PARAMETERS_ERROR_CODE = 'bad_parameters_error'

    def __init__(self, *args, **kwargs):
        super(BadParametersError, self).__init__(
            400, BadParametersError.BAD_PARAMETERS_ERROR_CODE, *args, **kwargs)


class InvalidBlueprintError(ManagerException):
    INVALID_BLUEPRINT_ERROR_CODE = 'invalid_blueprint_error'

    def __init__(self, *args, **kwargs):
        super(InvalidBlueprintError, self).__init__(
            400, InvalidBlueprintError.INVALID_BLUEPRINT_ERROR_CODE,
            *args, **kwargs)


class ExistingRunningExecutionError(ManagerException):
    EXISTING_RUNNING_EXECUTION_ERROR_CODE = 'existing_running_execution_error'

    def __init__(self, *args, **kwargs):
        super(ExistingRunningExecutionError, self).__init__(
            400, ExistingRunningExecutionError
            .EXISTING_RUNNING_EXECUTION_ERROR_CODE, *args, **kwargs)


class DeploymentWorkersNotYetInstalledError(ManagerException):
    DEPLOYMENT_WORKERS_NOT_YET_INSTALLED_ERROR_CODE = \
        'deployment_workers_not_yet_installed_error'

    def __init__(self, *args, **kwargs):
        super(DeploymentWorkersNotYetInstalledError, self).__init__(
            400,
            DeploymentWorkersNotYetInstalledError
            .DEPLOYMENT_WORKERS_NOT_YET_INSTALLED_ERROR_CODE,
            *args, **kwargs)


class IllegalActionError(ManagerException):
    ILLEGAL_ACTION_ERROR_CODE = 'illegal_action_error'

    def __init__(self, *args, **kwargs):
        super(IllegalActionError, self).__init__(
            400, IllegalActionError.ILLEGAL_ACTION_ERROR_CODE,
            *args, **kwargs)


class IllegalExecutionParametersError(ManagerException):
    ILLEGAL_EXECUTION_PARAMETERS_ERROR_CODE =\
        'illegal_execution_parameters_error'

    def __init__(self, *args, **kwargs):
        super(IllegalExecutionParametersError, self).__init__(
            400, IllegalExecutionParametersError.
            ILLEGAL_EXECUTION_PARAMETERS_ERROR_CODE,
            *args, **kwargs)


class NoSuchIncludeFieldError(ManagerException):
    NO_SUCH_INCLUDE_FIELD_ERROR = 'no_such_include_field_error'

    def __init__(self, *args, **kwargs):
        super(NoSuchIncludeFieldError, self).__init__(
            400,
            NoSuchIncludeFieldError.NO_SUCH_INCLUDE_FIELD_ERROR,
            *args,
            **kwargs
        )


class MissingRequiredDeploymentInputError(ManagerException):
    ERROR_CODE = 'missing_required_deployment_input_error'

    def __init__(self, *args, **kwargs):
        super(MissingRequiredDeploymentInputError, self).__init__(
            400,
            MissingRequiredDeploymentInputError.ERROR_CODE,
            *args,
            **kwargs
        )


class UnknownDeploymentInputError(ManagerException):
    ERROR_CODE = 'unknown_deployment_input_error'

    def __init__(self, *args, **kwargs):
        super(UnknownDeploymentInputError, self).__init__(
            400,
            UnknownDeploymentInputError.ERROR_CODE,
            *args,
            **kwargs
        )

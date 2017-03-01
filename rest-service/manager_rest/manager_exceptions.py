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


class InsufficientMemoryError(ManagerException):
    INSUFFICIENT_MEMORY_ERROR_CODE = 'insufficient_memory_error'

    def __init__(self, *args, **kwargs):
        super(InsufficientMemoryError, self).__init__(
            503, InsufficientMemoryError.INSUFFICIENT_MEMORY_ERROR_CODE,
            *args, **kwargs)


class MissingPremiumPackage(ManagerException):
    MISSING_PREMIUM_ERROR_CODE = 'missing_premium_package_error'

    def __init__(self, *args, **kwargs):
        super(MissingPremiumPackage, self).__init__(
            404, MissingPremiumPackage.MISSING_PREMIUM_ERROR_CODE,
            *args, **kwargs)


class ConflictError(ManagerException):
    CONFLICT_ERROR_CODE = 'conflict_error'

    def __init__(self, *args, **kwargs):
        super(ConflictError, self).__init__(
            409, ConflictError.CONFLICT_ERROR_CODE, *args, **kwargs)


class SQLStorageException(ManagerException):
    STORAGE_ERROR_CODE = 'storage_error'

    def __init__(self, *args, **kwargs):
        super(SQLStorageException, self).__init__(
            409, SQLStorageException.STORAGE_ERROR_CODE, *args, **kwargs)


class NotFoundError(ManagerException):
    NOT_FOUND_ERROR_CODE = 'not_found_error'

    def __init__(self, *args, **kwargs):
        super(NotFoundError, self).__init__(
            404, NotFoundError.NOT_FOUND_ERROR_CODE, *args, **kwargs)


class ParamUrlNotFoundError(ManagerException):
    PARAM_URL_NOT_FOUND_ERROR_CODE = 'param_url_not_found_error'

    def __init__(self, *args, **kwargs):
        super(ParamUrlNotFoundError, self).__init__(
            400, ParamUrlNotFoundError.PARAM_URL_NOT_FOUND_ERROR_CODE,
            *args, **kwargs)


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


class AppNotSecuredError(ManagerException):
    APP_NOT_SECURED_ERROR_CODE = 'application_not_secured_error'

    def __init__(self, *args, **kwargs):
        super(AppNotSecuredError, self).__init__(
            401, AppNotSecuredError.APP_NOT_SECURED_ERROR_CODE,
            *args, **kwargs)


class NoTokenGeneratorError(ManagerException):
    NO_TOKEN_GENERATOR_ERROR_CODE = 'no_token_generator_error'

    def __init__(self, *args, **kwargs):
        super(NoTokenGeneratorError, self).__init__(
            401, NoTokenGeneratorError.NO_TOKEN_GENERATOR_ERROR_CODE,
            *args, **kwargs)


class UnauthorizedError(ManagerException):
    UNAUTHORIZED_ERROR_CODE = 'unauthorized_error'

    def __init__(self, *args, **kwargs):
        super(UnauthorizedError, self).__init__(
            401, UnauthorizedError.UNAUTHORIZED_ERROR_CODE,
            *args, **kwargs)


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


class InvalidPluginError(ManagerException):
    INVALID_PLUGIN_ERROR_CODE = 'invalid_plugin_error'

    def __init__(self, *args, **kwargs):
        super(InvalidPluginError, self).__init__(
            400, InvalidPluginError.INVALID_PLUGIN_ERROR_CODE,
            *args, **kwargs)


class ExistingRunningExecutionError(ManagerException):
    EXISTING_RUNNING_EXECUTION_ERROR_CODE = 'existing_running_execution_error'

    def __init__(self, *args, **kwargs):
        super(ExistingRunningExecutionError, self).__init__(
            400, ExistingRunningExecutionError
            .EXISTING_RUNNING_EXECUTION_ERROR_CODE, *args, **kwargs)


class GlobalParallelRunningExecutionsLimitReachedError(ManagerException):
    GLOBAL_PARALLEL_RUNNING_EXECUTIONS_LIMIT_REACHED_ERROR_CODE = \
        'global_parallel_running_executions_limit_reached_error'

    def __init__(self, *args, **kwargs):
        super(GlobalParallelRunningExecutionsLimitReachedError, self).__init__(
            400,
            GlobalParallelRunningExecutionsLimitReachedError
            .GLOBAL_PARALLEL_RUNNING_EXECUTIONS_LIMIT_REACHED_ERROR_CODE,
            *args, **kwargs)


class InvalidExecutionUpdateStatus(ManagerException):
    INVALID_STATUS_UPDATE = 'invalid_exception_status_update'

    def __init__(self, *args, **kwargs):
        super(InvalidExecutionUpdateStatus, self).__init__(
            400,
            self.INVALID_STATUS_UPDATE,
            *args, **kwargs)


class UnsupportedChangeInDeploymentUpdate(ManagerException):
    UNSUPPORTED_CHANGE_IN_DEPLOYMENT_UPDATE = \
        'unsupported_change_in_deployment_update'

    def __init__(self, *args, **kwargs):
        super(UnsupportedChangeInDeploymentUpdate, self).__init__(
            400, UnsupportedChangeInDeploymentUpdate
            .UNSUPPORTED_CHANGE_IN_DEPLOYMENT_UPDATE, *args, **kwargs)


class ExistingStartedDeploymentModificationError(ManagerException):
    EXISTING_STARTED_DEPLOYMENT_MODIFICATION_ERROR = \
        'existing_started_deployment_modification_error'

    def __init__(self, *args, **kwargs):
        super(ExistingStartedDeploymentModificationError, self).__init__(
            400, ExistingStartedDeploymentModificationError
            .EXISTING_STARTED_DEPLOYMENT_MODIFICATION_ERROR, *args, **kwargs)


class DeploymentModificationAlreadyEndedError(ManagerException):
    DEPLOYMENT_MODIFICATION_ALREADY_ENDED_ERROR = \
        'deployment_modification_already_ended_error'

    def __init__(self, *args, **kwargs):
        super(DeploymentModificationAlreadyEndedError, self).__init__(
            400, DeploymentModificationAlreadyEndedError
            .DEPLOYMENT_MODIFICATION_ALREADY_ENDED_ERROR, *args, **kwargs)


class DeploymentEnvironmentCreationInProgressError(ManagerException):
    DEPLOYMENT_ENVIRONMENT_CREATION_IN_PROGRESS_ERROR_CODE = \
        'deployment_environment_creation_in_progress_error'

    def __init__(self, *args, **kwargs):
        super(DeploymentEnvironmentCreationInProgressError, self).__init__(
            400,
            DeploymentEnvironmentCreationInProgressError
            .DEPLOYMENT_ENVIRONMENT_CREATION_IN_PROGRESS_ERROR_CODE,
            *args, **kwargs)


class DeploymentEnvironmentCreationPendingError(ManagerException):
    DEPLOYMENT_ENVIRONMENT_CREATION_PENDING_ERROR_CODE = \
        'deployment_environment_creation_pending_error'

    def __init__(self, *args, **kwargs):
        super(DeploymentEnvironmentCreationPendingError, self).__init__(
            400,
            DeploymentEnvironmentCreationPendingError
            .DEPLOYMENT_ENVIRONMENT_CREATION_PENDING_ERROR_CODE,
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


class DeploymentOutputsEvaluationError(ManagerException):
    ERROR_CODE = 'deployment_outputs_evaluation_error'

    def __init__(self, *args, **kwargs):
        super(DeploymentOutputsEvaluationError, self).__init__(
            400,
            DeploymentOutputsEvaluationError.ERROR_CODE,
            *args,
            **kwargs
        )


class FunctionsEvaluationError(ManagerException):
    ERROR_CODE = 'functions_evaluation_error'

    def __init__(self, *args, **kwargs):
        super(FunctionsEvaluationError, self).__init__(
            400,
            FunctionsEvaluationError.ERROR_CODE,
            *args,
            **kwargs
        )


class UnknownModificationStageError(ManagerException):
    ERROR_CODE = 'unknown_modification_stage_error'

    def __init__(self, *args, **kwargs):
        super(UnknownModificationStageError, self).__init__(
            400,
            UnknownModificationStageError.ERROR_CODE,
            *args,
            **kwargs
        )


class ResolverInstantiationError(ManagerException):
    ERROR_CODE = 'resolver_instantiation_error'

    def __init__(self, *args, **kwargs):
        super(ResolverInstantiationError, self).__init__(
            400,
            ResolverInstantiationError.ERROR_CODE,
            *args,
            **kwargs
        )


class MethodNotAllowedError(ManagerException):
    ERROR_CODE = 'method_not_allowed_error'

    def __init__(self, *args, **kwargs):
        super(MethodNotAllowedError, self).__init__(
            405,
            MethodNotAllowedError.ERROR_CODE,
            *args,
            **kwargs
        )


class SnapshotActionError(ManagerException):
    ERROR_CODE = 'snapshot_action_error'

    def __init__(self, *args, **kwargs):
        super(SnapshotActionError, self).__init__(
            400,
            SnapshotActionError.ERROR_CODE,
            *args,
            **kwargs
        )


class PluginInUseError(ManagerException):
    ERROR_CODE = 'plugin_in_use'

    def __init__(self, *args, **kwargs):
        super(PluginInUseError, self).__init__(
            405,
            PluginInUseError.ERROR_CODE,
            *args,
            **kwargs
        )


class PluginInstallationError(ManagerException):
    ERROR_CODE = 'plugin_installation_error'

    def __init__(self, *args, **kwargs):
        super(PluginInstallationError, self).__init__(
                400,
                PluginInstallationError.ERROR_CODE,
                *args,
                **kwargs
        )


class PluginInstallationTimeout(ManagerException):
    ERROR_CODE = 'plugin_installation_timeout'

    def __init__(self, *args, **kwargs):
        super(PluginInstallationTimeout, self).__init__(
            400,
            PluginInstallationTimeout.ERROR_CODE,
            *args,
            **kwargs
        )


class ExecutionFailure(RuntimeError):
    pass


class ExecutionTimeout(RuntimeError):
    pass


class DslParseException(Exception):
    pass


class BlueprintAlreadyExistsException(Exception):
    def __init__(self, blueprint_id, *args):
        Exception.__init__(self, args)
        self.blueprint_id = blueprint_id


class DeploymentPluginNotFound(ManagerException):
    """ Raised when a plugin is listed in the blueprint but not installed
        on the manager"""
    ERROR_CODE = 'deployment_plugin_not_found'

    def __init__(self, *args, **kwargs):
        super(DeploymentPluginNotFound, self).__init__(
            412,
            DeploymentPluginNotFound.ERROR_CODE,
            *args,
            **kwargs
        )

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

import typing

from flask import jsonify

INTERNAL_SERVER_ERROR_CODE = 'internal_server_error'


class ManagerException(Exception):
    additional_headers: typing.ClassVar[dict[str, str]] = {}
    error_code = INTERNAL_SERVER_ERROR_CODE
    status_code = 500

    def to_response(self):
        return jsonify(
            message=str(self),
            error_code=self.error_code,
            # useless, but v1 and v2 api clients require server_traceback
            # remove this after dropping v1 and v2 api clients
            server_traceback=None
        )


class UnknownAction(ManagerException):
    error_code = 'unknown_action'
    status_code = 400


class InsufficientMemoryError(ManagerException):
    error_code = 'insufficient_memory_error'
    status_code = 503


class SystemInSnapshotRestoreError(ManagerException):
    error_code = 'in_snapshot_restore_error'
    status_code = 503


class FileSyncServiceError(ManagerException):
    error_code = 'file_sync_service_error'
    status_code = 503


class MissingPremiumPackage(ManagerException):
    error_code = 'missing_premium_package_error'
    status_code = 404

    def __init__(self, *args, **kwargs):
        message = ('This feature exists only in the premium edition of '
                   'Cloudify.\nPlease contact sales for additional info.')
        super().__init__(message, *args, **kwargs)


class CommunityOnly(ManagerException):
    error_code = 'community_only_error'
    status_code = 404

    def __init__(self, *args, **kwargs):
        message = ('This feature exists only in the community edition of '
                   'Cloudify.')
        super().__init__(message, *args, **kwargs)


class ConflictError(ManagerException):
    error_code = 'conflict_error'
    status_code = 409


class AmbiguousName(ManagerException):
    error_code = 'ambiguous_name'
    status_code = 409


class SQLStorageException(ManagerException):
    error_code = 'storage_error'
    status_code = 409


class NotFoundError(ManagerException):
    error_code = 'not_found_error'
    status_code = 404


class ParamUrlNotFoundError(ManagerException):
    error_code = 'param_url_not_found_error'
    status_code = 400


class DependentExistsError(ManagerException):
    error_code = 'dependent_exists_error'
    status_code = 400


class DeploymentParentNotFound(ManagerException):
    error_code = 'deployment_parent_not_found_error'
    status_code = 404


class NonexistentWorkflowError(ManagerException):
    error_code = 'nonexistent_workflow_error'
    status_code = 400


class UnavailableWorkflowError(ManagerException):
    error_code = 'unavailable_workflow_error'
    status_code = 400


class InvalidWorkflowAvailabilityRule(ManagerException):
    error_code = 'invalid_workflow_availability_rule_error'
    status_code = 400


class AppNotSecuredError(ManagerException):
    error_code = 'application_not_secured_error'
    status_code = 401


class NoTokenGeneratorError(ManagerException):
    error_code = 'no_token_generator_error'
    status_code = 401


class InvalidFernetTokenFormatError(ManagerException):
    error_code = 'invalid_fernet_token_format_error'
    status_code = 500


class UnauthorizedError(ManagerException):
    error_code = 'unauthorized_error'
    status_code = 401

    def __init__(self, extra_info, *args, **kwargs):
        message = 'User unauthorized'
        if extra_info:
            message = f'{message}: {extra_info}'
        super().__init__(message, *args, **kwargs)


class NoAuthProvided(UnauthorizedError):
    """Not authorized, because authentication was not provided."""
    def __init__(self, *args, **kwargs):
        super().__init__('No authentication info provided', *args, **kwargs)


class ForbiddenError(ManagerException):
    error_code = 'forbidden_error'
    status_code = 403


class ForbiddenWhileCancelling(ForbiddenError):
    error_code = 'forbidden_while_cancelling'


class OnlyDeploymentUpdate(ForbiddenError):
    """This request is only allowed from a deployment-update workflow."""
    error_code = 'only_deployment_update'


class UnsupportedContentTypeError(ManagerException):
    error_code = 'unsupported_content_type_error'
    status_code = 415


class BadParametersError(ManagerException):
    error_code = 'bad_parameters_error'
    status_code = 400


class InvalidBlueprintError(ManagerException):
    error_code = 'invalid_blueprint_error'
    status_code = 400


class InvalidPluginError(ManagerException):
    error_code = 'invalid_plugin_error'
    status_code = 400


class ExistingRunningExecutionError(ManagerException):
    error_code = 'existing_running_execution_error'
    status_code = 400


class GlobalParallelRunningExecutionsLimitReachedError(ManagerException):
    error_code = 'global_parallel_running_executions_limit_reached_error'
    status_code = 400


class InvalidExecutionUpdateStatus(ManagerException):
    error_code = 'invalid_exception_status_update'
    status_code = 400


class UnsupportedChangeInDeploymentUpdate(ManagerException):
    error_code = 'unsupported_change_in_deployment_update'
    status_code = 400


class PluginsUpdateError(ManagerException):
    error_code = 'plugins_update_failed'
    status_code = 400


class ExistingStartedDeploymentModificationError(ManagerException):
    error_code = 'existing_started_deployment_modification_error'
    status_code = 400


class DeploymentModificationAlreadyEndedError(ManagerException):
    error_code = 'deployment_modification_already_ended_error'
    status_code = 400


class IllegalActionError(ManagerException):
    error_code = 'illegal_action_error'
    status_code = 400


class IllegalExecutionParametersError(ManagerException):
    error_code = 'illegal_execution_parameters_error'
    status_code = 400


class NoSuchIncludeFieldError(ManagerException):
    error_code = 'no_such_include_field_error'
    status_code = 400


class DeploymentCreationError(ManagerException):
    """An error during create-deployment-environment"""
    error_code = 'deployment_creation_error'
    status_code = 400


class DeploymentEnvironmentCreationInProgressError(ManagerException):
    error_code = 'deployment_environment_creation_in_progress_error'
    status_code = 400


class DeploymentEnvironmentCreationPendingError(ManagerException):
    error_code = 'deployment_environment_creation_pending_error'
    status_code = 400


class MissingRequiredDeploymentInputError(ManagerException):
    error_code = 'missing_required_deployment_input_error'
    status_code = 400


class UnknownDeploymentInputError(ManagerException):
    error_code = 'unknown_deployment_input_error'
    status_code = 400


class DeploymentInputEvaluationError(ManagerException):
    error_code = 'deployment_input_evaluation_error'
    status_code = 400


class ConstraintError(ManagerException):
    error_code = 'constraint_error'
    status_code = 400


class UnknownDeploymentSecretError(ManagerException):
    error_code = 'unknown_deployment_secret_error'
    status_code = 400


class UnsupportedDeploymentGetSecretError(ManagerException):
    error_code = 'unknown_deployment_secret_error'
    status_code = 400


class DeploymentOutputsEvaluationError(ManagerException):
    error_code = 'deployment_outputs_evaluation_error'
    status_code = 400


class DeploymentCapabilitiesEvaluationError(ManagerException):
    error_code = 'deployment_capabilities_evaluation_error'
    status_code = 400


class FunctionsEvaluationError(ManagerException):
    error_code = 'functions_evaluation_error'
    status_code = 400


class UnknownModificationStageError(ManagerException):
    error_code = 'unknown_modification_stage_error'
    status_code = 400


class ResolverInstantiationError(ManagerException):
    error_code = 'resolver_instantiation_error'
    status_code = 400


class MethodNotAllowedError(ManagerException):
    error_code = 'method_not_allowed_error'
    status_code = 405


class SnapshotActionError(ManagerException):
    error_code = 'snapshot_action_error'
    status_code = 400


class LogBundleActionError(ManagerException):
    error_code = 'log_bundle_action_error'
    status_code = 400


class PluginInUseError(ManagerException):
    error_code = 'plugin_in_use'
    status_code = 405


class BlueprintInUseError(ManagerException):
    error_code = 'blueprint_in_use'
    status_code = 405


class PluginInstallationError(ManagerException):
    error_code = 'plugin_installation_error'
    status_code = 400


class PluginInstallationTimeout(ManagerException):
    error_code = 'plugin_installation_timeout'
    status_code = 400


class UploadFileMissing(ManagerException):
    error_code = 'upload_missing_file'
    status_code = 400


class PluginDistributionNotSupported(PluginInstallationError):
    pass


class ExecutionFailure(RuntimeError):
    pass


class ExecutionTimeout(RuntimeError):
    pass


class DslParseException(Exception):
    pass


class ArchiveTypeError(RuntimeError):
    pass


class BlueprintAlreadyExistsException(Exception):
    def __init__(self, blueprint_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.blueprint_id = blueprint_id


class ImportedBlueprintNotFound(ManagerException):
    error_code = 'imported_blueprint_not_found'
    status_code = 404


class DeploymentPluginNotFound(ManagerException):
    """A plugin is listed in the blueprint but not installed on the manager"""
    error_code = 'deployment_plugin_not_found'
    status_code = 400


class TenantNotProvided(ForbiddenError):
    pass


class IncompatibleClusterArchitectureError(ManagerException):
    """Node is trying to join a cluster with a different architecture

    eg. node A is all-in-one and node B has an external database
    """
    error_code = 'incompatible_cluster_architecture'
    status_code = 400


class InvalidCloudifyLicense(ManagerException):
    """The uploaded Cloudify license can't be verified.

    This can happen when:
    1. The license has been tampered and the signature does not
       match.
    2. The license version is older than the Manager`s version.
    """
    error_code = 'unverified_cloudify_license'
    status_code = 400


class InvalidYamlFormat(ManagerException):
    error_code = 'invalid_yaml_format'
    status_code = 400


class BadFilterRule(ManagerException):
    error_code = 'invalid_filter_rule'
    status_code = 400

    def __init__(self, err_filter_rule, suffix='', *args, **kwargs):
        super().__init__(
            f"The filter rule {err_filter_rule} is not in the right format. "
            f"{suffix}",
            *args,
            **kwargs
        )
        self.err_filter_rule = err_filter_rule
        self.error_reason = suffix

    def to_response(self):
        return jsonify(
            message=str(self),
            error_code=self.error_code,
            # useless, but v1 and v2 api clients require server_traceback
            # remove this after dropping v1 and v2 api clients
            server_traceback=None,
            err_filter_rule=self.err_filter_rule,
            err_reason=self.error_reason
        )


class FailedDependency(ManagerException):
    error_code = 'failed_dependency'
    status_code = 400


class NotListeningLDAPServer(ManagerException):
    error_code = 'not_running_ldap_server'
    status_code = 500


class UnsupportedFileServerType(ManagerException):
    error_code = 'unsupported_file_server_type'
    status_code = 500


class FileServerException(ManagerException):
    error_code = 'file_server_exception'
    status_code = 500

import uuid
from builtins import staticmethod

from flask import request
from flask_restful.inputs import boolean
from flask_restful_swagger import swagger
from flask_restful.reqparse import Argument
from sqlalchemy import and_ as sql_and


from cloudify._compat import text_type
from cloudify.models_states import (VisibilityState,
                                    ExecutionState,
                                    BlueprintUploadState,
                                    )
from cloudify.deployment_dependencies import (create_deployment_dependency,
                                              DEPENDENCY_CREATOR,
                                              SOURCE_DEPLOYMENT,
                                              TARGET_DEPLOYMENT,
                                              TARGET_DEPLOYMENT_FUNC)

from manager_rest import utils, manager_exceptions, workflow_executor
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import (authorize,
                                                 check_user_action_allowed)
from manager_rest.storage import db, models, get_storage_manager
from manager_rest.manager_exceptions import (
    DeploymentEnvironmentCreationInProgressError,
    DeploymentCreationError,
    BadParametersError,
    IllegalActionError,
    ConflictError)
from manager_rest.resource_manager import get_resource_manager
from manager_rest.maintenance import is_bypass_maintenance_mode
from manager_rest.dsl_functions import evaluate_deployment_capabilities
from manager_rest.execution_token import current_execution

from manager_rest.rest.filters_utils import get_filter_rules_from_filter_id
from manager_rest.rest import (
    rest_utils,
    resources_v1,
    rest_decorators,
    responses_v3
)
from ..responses_v2 import ListResponse


SHARED_RESOURCE_TYPE = 'cloudify.nodes.SharedResource'
COMPONENT_TYPE = 'cloudify.nodes.Component'
EXTERNAL_SOURCE = 'external_source'
EXTERNAL_TARGET = 'external_target'


class DeploymentsId(resources_v1.DeploymentsId):

    def create_request_schema(self):
        request_schema = super(DeploymentsId, self).create_request_schema()
        request_schema['skip_plugins_validation'] = {
            'optional': True, 'type': bool}
        request_schema['site_name'] = {'optional': True, 'type': text_type}
        request_schema['runtime_only_evaluation'] = {
            'optional': True, 'type': bool
        }
        request_schema['display_name'] = {'optional': True, 'type': text_type}
        return request_schema

    def get_skip_plugin_validation_flag(self, request_dict):
        return request_dict.get('skip_plugins_validation', False)

    def _error_from_create(self, execution):
        """Map a failed create-dep-env execution to a REST error response"""
        if execution.status != ExecutionState.FAILED or not execution.error:
            return DeploymentEnvironmentCreationInProgressError()
        error_message = execution.error.strip().split('\n')[-1]
        return DeploymentCreationError(error_message)

    @staticmethod
    def _populate_direct_deployment_counts_and_statuses(deployment):
        sm = get_storage_manager()
        sub_services_count = 0
        sub_environments_count = 0
        sub_services_status = None
        sub_environments_status = None
        sources = sm.list(
            models.DeploymentLabelsDependencies,
            filters={
                'target_deployment_id': deployment['id']
            },
            get_all_results=True
        )
        for source in sources:
            _dep = source.source_deployment
            _dep_status = _dep.evaluate_deployment_status(
                exclude_sub_deployments=True)
            if _dep.is_environment:
                sub_environments_count += 1
                sub_environments_status = _dep.compare_statuses(
                    sub_environments_status,
                    _dep_status
                )
            else:
                sub_services_count += 1
                sub_services_status = _dep.compare_statuses(
                    sub_services_status,
                    _dep_status
                )
        deployment['sub_environments_count'] = sub_environments_count
        deployment['sub_services_count'] = sub_services_count
        deployment['sub_environments_status'] = sub_environments_status
        deployment['sub_services_status'] = sub_services_status
        return deployment

    @staticmethod
    def _update_labels_for_deployment(rm, deployment, new_labels,
                                      creator=None, created_at=None):
        sm = get_storage_manager()
        deployment_parents = deployment.deployment_parents
        new_parents = rm.get_deployment_parents_from_labels(new_labels)

        parents_to_remove = [sm.get(models.Deployment, parent_id)
                             for parent_id in
                             set(deployment_parents) - set(new_parents)]

        rm.update_resource_labels(
            models.DeploymentLabel,
            deployment,
            new_labels,
            creator=creator,
            created_at=created_at,
        )

        rm.delete_deployment_from_labels_graph([deployment], parents_to_remove)
        rm.add_deployment_to_labels_graph(
            [deployment], set(new_parents) - set(deployment_parents))
        to_upd = set()
        if parents_to_remove:
            to_upd |= {p._storage_id for p in parents_to_remove}
        if new_parents:
            to_upd.add(deployment._storage_id)
        return to_upd

    def _handle_deployment_labels(self, sm, rm, deployment, raw_labels_list,
                                  creator=None, created_at=None):
        new_labels = rest_utils.get_labels_list(raw_labels_list)
        if self._is_create_execution(deployment):
            self._add_existing_labels(deployment, new_labels)

        return self._update_labels_for_deployment(rm, deployment, new_labels,
                                                  creator=creator,
                                                  created_at=created_at)

    def _is_create_execution(self, deployment):
        """Are we running in deployment's create execution?"""
        return current_execution and \
            current_execution == deployment.create_execution

    def _add_existing_labels(self, deployment, new_labels):
        """Add existing deployment labels to new_labels.

        This is to be run during the set-labels executed as part of
        create-deployment-environment, so that we don't overwrite labels
        attached to the deployment (directly or via a group) while
        create-deployment-environment was running.
        Instead, the labels attached in the meantime, are considered to be
        part of the new labels set as well.
        """
        old_labels = [(label.key, label.value) for label in deployment.labels]
        for label in old_labels:
            if label not in new_labels:
                new_labels.append(label)

    @authorize('deployment_create')
    @rest_decorators.marshal_with(models.Deployment)
    @rest_decorators.not_while_cancelling
    def put(self, deployment_id, **kwargs):
        """
        Create a deployment
        """
        rest_utils.validate_inputs({'deployment_id': deployment_id},
                                   validate_value_begins_with_letter=False)
        request_schema = self.create_request_schema()
        request_dict = rest_utils.get_json_and_verify_params(request_schema)
        blueprint_id = request_dict['blueprint_id']
        bypass_maintenance = is_bypass_maintenance_mode()
        args = rest_utils.get_args_and_verify_arguments([
            Argument('private_resource', type=boolean),
            Argument('async_create', type=boolean, default=False)
        ])
        visibility = rest_utils.get_visibility_parameter(
            optional=True,
            valid_values=VisibilityState.STATES
        )
        labels = rest_utils.get_labels_list(request_dict.get('labels', []))
        inputs = request_dict.get('inputs', {})
        skip_plugins_validation = self.get_skip_plugin_validation_flag(
            request_dict)
        rm = get_resource_manager()
        sm = get_storage_manager()
        blueprint = sm.get(models.Blueprint, blueprint_id)
        if blueprint.state != BlueprintUploadState.UPLOADED:
            raise DeploymentCreationError(
                'Unable to create a deployment based on a blueprint which is '
                f'not `uploaded` but: `{blueprint.state}`')
        site_name = _get_site_name(request_dict)
        site = sm.get(models.Site, site_name) if site_name else None

        rm.cleanup_failed_deployment(deployment_id)
        with sm.transaction():
            if not skip_plugins_validation:
                rm.check_blueprint_plugins_installed(blueprint.plan)
            deployment = rm.create_deployment(
                blueprint,
                deployment_id,
                private_resource=args.private_resource,
                visibility=visibility,
                site=site,
                runtime_only_evaluation=request_dict.get(
                    'runtime_only_evaluation', False),
            )
            create_execution = deployment.make_create_environment_execution(
                inputs=inputs,
                labels=labels,
                display_name=request_dict.get('display_name'),
            )
            try:
                messages = rm.prepare_executions(
                    [create_execution],
                    bypass_maintenance=bypass_maintenance,
                    commit=False
                )
            except manager_exceptions.ExistingRunningExecutionError:
                rm.delete_deployment(deployment)
                raise
        workflow_executor.execute_workflow(messages)
        if not args.async_create:
            rest_utils.wait_for_execution(sm, deployment.create_execution.id)
            if deployment.create_execution.status != ExecutionState.TERMINATED:
                raise self._error_from_create(deployment.create_execution)
        return deployment, 201

    @authorize('deployment_update')
    @rest_decorators.marshal_with(models.Deployment)
    def patch(self, deployment_id):
        """Update a deployment, setting attributes and labels.
        """
        if not request.json:
            raise IllegalActionError('Update a deployment request must include'
                                     ' at least one parameter to update')
        request_dict = request.json
        creator = None
        if 'creator' in request_dict:
            check_user_action_allowed('set_owner', None, True)
            creator = rest_utils.valid_user(request_dict['creator'])
        created_at = None
        if request_dict.get('created_at'):
            check_user_action_allowed('set_timestamp', None, True)
            created_at = rest_utils.parse_datetime_string(
                request_dict['created_at'])
        sm = get_storage_manager()
        rm = get_resource_manager()
        with sm.transaction():
            deployment = sm.get(models.Deployment, deployment_id, locking=True)
            allowed_attribs = {
                'description', 'workflows', 'inputs', 'policy_types',
                'policy_triggers', 'groups', 'scaling_groups', 'outputs',
                'capabilities', 'display_name',
            }
            allow_change = {'display_name'}
            for attrib in allowed_attribs:
                if attrib not in request_dict:
                    continue
                previous = getattr(deployment, attrib, None)
                if rest_utils.is_deployment_update():
                    change_allowed = True
                else:
                    change_allowed = attrib in allow_change
                if previous is not None and not change_allowed:
                    raise ConflictError(f'{attrib} is already set')
                setattr(deployment, attrib, request_dict[attrib])
            if 'blueprint_id' in request_dict:
                if not rest_utils.is_deployment_update():
                    raise manager_exceptions.OnlyDeploymentUpdate(
                        'Changing the blueprint is only possible via '
                        'deployment-update')
                deployment.blueprint = sm.get(
                    models.Blueprint, request_dict['blueprint_id'])
            if creator:
                deployment.creator = creator
            to_upd = None
            if 'labels' in request_dict:
                raw_labels_list = request_dict.get('labels', [])
                to_upd = self._handle_deployment_labels(
                    sm,
                    rm,
                    deployment,
                    raw_labels_list,
                    creator=creator,
                    created_at=created_at,
                )
            sm.update(deployment)
        if to_upd:
            rm.recalc_ancestors(to_upd)
        return deployment

    @authorize('deployment_get')
    @rest_decorators.marshal_with(models.Deployment)
    def get(self, deployment_id, _include=None, **kwargs):
        args = rest_utils.get_args_and_verify_arguments([
            Argument('all_sub_deployments', type=boolean, default=True),
        ])
        if not args.all_sub_deployments \
                and _include and ('id' not in _include):
            # we will need to use id in the _populate_direct method, so it
            # must be included
            _include.append('id')
        deployment = get_storage_manager().get(
            models.Deployment, deployment_id, include=_include)
        # always return the deployment if `all_sub_deployments` is True
        if args.all_sub_deployments:
            return deployment
        deployment = deployment.to_response(include=_include)
        return self._populate_direct_deployment_counts_and_statuses(deployment)


class DeploymentsSetVisibility(SecuredResource):

    @authorize('deployment_set_visibility')
    @rest_decorators.marshal_with(models.Deployment)
    def patch(self, deployment_id):
        """
        Set the deployment's visibility
        """
        visibility = rest_utils.get_visibility_parameter()
        return get_resource_manager().set_deployment_visibility(
            deployment_id,
            visibility
        )


class DeploymentsIdCapabilities(SecuredResource):

    @swagger.operation(
        responseClass=responses_v3.DeploymentCapabilities.__name__,
        nickname="get",
        notes="Gets a specific deployment's capabilities."
    )
    @authorize('deployment_capabilities')
    @rest_decorators.marshal_with(responses_v3.DeploymentCapabilities)
    def get(self, deployment_id, **kwargs):
        """Get deployment capabilities"""
        capabilities = evaluate_deployment_capabilities(deployment_id)
        return dict(deployment_id=deployment_id, capabilities=capabilities)


class DeploymentsSetSite(SecuredResource):

    @authorize('deployment_set_site')
    @rest_decorators.marshal_with(models.Deployment)
    def post(self, deployment_id):
        """
        Set the deployment's site
        """
        site_name = _get_site_name(request.json)
        storage_manager = get_storage_manager()
        deployment = storage_manager.get(models.Deployment, deployment_id)
        site = None
        if site_name:
            site = storage_manager.get(models.Site, site_name)
            utils.validate_deployment_and_site_visibility(deployment, site)
        self._validate_detach_site(site_name)
        deployment.site = site
        return storage_manager.update(deployment)

    def _validate_detach_site(self, site_name):
        detach_site = request.json.get('detach_site')
        if (site_name and detach_site) or (not site_name and not detach_site):
            raise BadParametersError(
                "Must provide either a `site_name` of a valid site or "
                "`detach_site` with true value for detaching the current "
                "site of the given deployment"
            )


def _get_site_name(request_dict):
    if 'site_name' not in request_dict:
        return None

    site_name = request_dict['site_name']
    rest_utils.validate_inputs({'site_name': site_name})
    return site_name


class InterDeploymentDependencies(SecuredResource):
    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesCreate",
        notes="Creates an inter-deployment dependency.",
        parameters=utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'deployment_dependency')
    )
    @authorize('inter_deployment_dependency_create')
    @rest_decorators.marshal_with(models.InterDeploymentDependencies)
    def put(self):
        """Creates an inter-deployment dependency.

        :param dependency_creator: a string representing the entity that
         is responsible for this dependency (e.g. an intrinsic function
         blueprint path, 'node_instances.some_node_instance', etc.).
        :param source_deployment: source deployment that depends on the target
         deployment.
        :param target_deployment: the deployment that the source deployment
         depends on.
        :param target_deployment_func: a function used to determine the target
        deployment.
        :param external_source: metadata, in JSON format, of the source
        deployment (deployment name, tenant name, and the manager host(s)),
        in case it resides on an external manager. None otherwise
        :param external_target: metadata, in JSON format, of the target
        deployment (deployment name, tenant name, and the manager host(s)),
        in case it resides on an external manager. None otherwise
        :return: an InterDeploymentDependency object containing the information
         of the dependency.
        """
        sm = get_storage_manager()

        params = self._get_put_dependency_params(sm)
        now = utils.get_formatted_timestamp()

        if (TARGET_DEPLOYMENT in params and
                EXTERNAL_SOURCE not in params and
                EXTERNAL_TARGET not in params):
            # assert no cyclic dependencies are created
            dependents = params[SOURCE_DEPLOYMENT].get_all_dependents()
            if params[TARGET_DEPLOYMENT] in dependents:
                raise manager_exceptions.ConflictError(
                    f'cyclic dependency between deployments '
                    f'{params[SOURCE_DEPLOYMENT].id} '
                    f'and {params[TARGET_DEPLOYMENT].id}'
                )

        source_deployment = None if EXTERNAL_SOURCE in params \
            else params[SOURCE_DEPLOYMENT]

        deployment_dependency = models.InterDeploymentDependencies(
            id=str(uuid.uuid4()),
            dependency_creator=params[DEPENDENCY_CREATOR],
            source_deployment=source_deployment,
            target_deployment=params.get(TARGET_DEPLOYMENT),
            target_deployment_func=params.get(TARGET_DEPLOYMENT_FUNC),
            external_source=params.get(EXTERNAL_SOURCE),
            external_target=params.get(EXTERNAL_TARGET),
            created_at=now)
        return sm.put(deployment_dependency)

    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesCreate",
        notes="Creates a batch of inter-deployment dependency.",
        parameters=list(utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'deployment_dependency'))
    )
    @authorize('inter_deployment_dependency_create')
    @rest_decorators.marshal_list_response
    def post(self):
        """Creates an inter-deployment dependency.

        :param source_deployment_id: ID of the source deployment
         (the one which depends on the target deployment).
        :param inter_deployment_dependencies: a list containing
         inter_deployment_dependencies descriptions.
        :return: a list of InterDeploymentDependency IDs.
        """
        sm = get_storage_manager()

        params = rest_utils.get_json_and_verify_params({
            'source_deployment_id': {'type': str},
            'inter_deployment_dependencies': {'type': list}
        })

        dependencies = params.get('inter_deployment_dependencies')
        if len(dependencies) > 0 and EXTERNAL_SOURCE in dependencies[0]:
            source_deployment = None
        else:
            source_deployment = sm.get(models.Deployment,
                                       params['source_deployment_id'])

        created_ids = []
        with sm.transaction():
            for dependency in dependencies:
                record = _create_inter_deployment_dependency(
                    source_deployment, dependency, sm)
                created_ids += [record.id]

        return ListResponse(
            items=[{'id': i} for i in created_ids],
            metadata={'pagination': {
                'total': len(created_ids),
                'size': len(created_ids),
                'offset': 0,
            }}
        )

    @staticmethod
    def _verify_and_get_source_and_target_deployments(
            sm,
            source_deployment_id,
            target_deployment_id,
            target_deployment_func=None,
            is_component_deletion=False,
            external_source=None,
            external_target=None):

        if external_source:
            source_deployment = None
        else:
            source_deployment = sm.get(models.Deployment,
                                       source_deployment_id,
                                       fail_silently=True,
                                       all_tenants=True)
            if not source_deployment:
                raise manager_exceptions.NotFoundError(
                    'Given source deployment with ID `{0}` does not '
                    'exist.'.format(source_deployment_id)
                )
        if target_deployment_id:
            target_deployment = sm.get(models.Deployment,
                                       target_deployment_id,
                                       fail_silently=True,
                                       all_tenants=True)
        else:
            target_deployment = None
        if not (is_component_deletion or external_source or
                external_target or target_deployment_func or
                target_deployment):
            raise manager_exceptions.NotFoundError(
                'Given target deployment with ID `{0}` does not '
                'exist.  Also the target deployment function has '
                'not been provided'.format(target_deployment_id)
            )
        return source_deployment, target_deployment

    @staticmethod
    def _verify_dependency_params():
        return rest_utils.get_json_and_verify_params({
            DEPENDENCY_CREATOR: {'type': text_type},
            SOURCE_DEPLOYMENT: {'type': text_type},
            TARGET_DEPLOYMENT: {'optional': True, 'type': text_type},
            TARGET_DEPLOYMENT_FUNC: {'optional': True, 'type': dict},
            EXTERNAL_SOURCE: {'optional': True, 'type': dict},
            EXTERNAL_TARGET: {'optional': True, 'type': dict},
        })

    @staticmethod
    def _get_put_dependency_params(sm):
        request_dict = InterDeploymentDependencies._verify_dependency_params()
        target_deployment_func = request_dict.get(TARGET_DEPLOYMENT_FUNC)
        external_source = request_dict.get(EXTERNAL_SOURCE)
        external_target = request_dict.get(EXTERNAL_TARGET)
        source_deployment, target_deployment = InterDeploymentDependencies. \
            _verify_and_get_source_and_target_deployments(
                sm,
                request_dict.get(SOURCE_DEPLOYMENT),
                request_dict.get(TARGET_DEPLOYMENT),
                target_deployment_func=target_deployment_func,
                external_source=external_source,
                external_target=external_target
            )
        dependency_params = create_deployment_dependency(
            request_dict.get(DEPENDENCY_CREATOR),
            source_deployment,
            target_deployment,
            target_deployment_func=target_deployment_func,
            external_source=external_source,
            external_target=external_target)
        return dependency_params

    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesDelete",
        notes="Deletes an inter-deployment dependency.",
        parameters=utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'deployment_dependency')
    )
    @authorize('inter_deployment_dependency_delete')
    def delete(self):
        """Deletes an inter-deployment dependency.

        :param dependency_creator: a string representing the entity that
         is responsible for this dependency (e.g. an intrinsic function
         blueprint path, 'node_instances.some_node_instance', etc.).
        :param source_deployment: source deployment that depends on the target
         deployment.
        :param target_deployment: the deployment that the source deployment
         depends on.
        :param is_component_deletion: a special flag for allowing the
         deletion of a Component inter-deployment dependency when the target
         deployment is already deleted.
        :param external_source: metadata, in JSON format, of the source
        deployment (deployment name, tenant name, and the manager host(s)),
        in case it resides on an external manager. None otherwise
        :param external_target: metadata, in JSON format, of the target
        deployment (deployment name, tenant name, and the manager host(s)),
        in case it resides on an external manager. None otherwise
        :return: an InterDeploymentDependency object containing the information
         of the dependency.
        """
        sm = get_storage_manager()
        params = self._get_delete_dependency_params(sm)
        filters = create_deployment_dependency(
            params[DEPENDENCY_CREATOR],
            params.get(SOURCE_DEPLOYMENT),
            params.get(TARGET_DEPLOYMENT),
            external_source=params.get(EXTERNAL_SOURCE))
        dependency = sm.get(
            models.InterDeploymentDependencies,
            None,
            filters=filters,
            # Locking to make sure to fail here and not during the deletion
            # (for the purpose of clarifying the error in case one occurs).
            locking=True)

        sm.delete(dependency)
        return None, 204

    @staticmethod
    def _get_delete_dependency_params(sm):
        request_dict = InterDeploymentDependencies._verify_dependency_params()
        external_source = request_dict.get(EXTERNAL_SOURCE)
        external_target = request_dict.get(EXTERNAL_TARGET)
        source_deployment, target_deployment = InterDeploymentDependencies. \
            _verify_and_get_source_and_target_deployments(
                sm,
                request_dict.get(SOURCE_DEPLOYMENT),
                request_dict.get(TARGET_DEPLOYMENT),
                external_source=external_source,
                external_target=external_target,
                is_component_deletion=request_dict['is_component_deletion']
            )
        dependency_params = create_deployment_dependency(
            request_dict.get(DEPENDENCY_CREATOR),
            source_deployment,
            target_deployment,
            external_source=external_source,
            external_target=external_target)
        return dependency_params

    @swagger.operation(
        responseClass='List[{0}]'.format(
            models.InterDeploymentDependencies.__name__),
        nickname="listInterDeploymentDependencies",
        notes='Returns a list of inter-deployment dependencies',
        parameters=utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'inter-deployment dependency'
        )
    )
    @authorize('inter_deployment_dependency_list')
    @rest_decorators.marshal_with(models.InterDeploymentDependencies)
    @rest_decorators.create_filters(models.InterDeploymentDependencies)
    @rest_decorators.paginate
    @rest_decorators.sortable(models.InterDeploymentDependencies)
    @rest_decorators.search('id')
    def get(self,
            _include=None,
            filters=None,
            pagination=None,
            sort=None,
            search=None,
            **_):
        """List inter-deployment dependencies"""
        inter_deployment_dependencies = \
            get_storage_manager().list(
                models.InterDeploymentDependencies,
                include=_include,
                filters=filters,
                pagination=pagination,
                sort=sort,
                substr_filters=search
            )
        return inter_deployment_dependencies


class InterDeploymentDependenciesId(SecuredResource):
    @swagger.operation(
        responseClass=models.InterDeploymentDependencies,
        nickname="DeploymentDependenciesUpdate",
        notes="Rewrites inter-deployment dependencies for deployment_id.",
        parameters=list(utils.create_filter_params_list_description(
            models.InterDeploymentDependencies.response_fields,
            'deployment_dependency'))
    )
    @authorize('inter_deployment_dependency_create')  # TODO: '..._update'
    @rest_decorators.marshal_list_response
    def put(self, deployment_id):
        """Updates an inter-deployment dependency for given deployment.

        :param deployment_id: ID of the source deployment
         (the one which depends on the target deployment).
        :param inter_deployment_dependencies: a list containing
         inter_deployment_dependencies descriptions.
        :return: a list of InterDeploymentDependency IDs.
        """
        sm = get_storage_manager()

        params = rest_utils.get_json_and_verify_params({
            'inter_deployment_dependencies': {'type': list}
        })

        dependencies = params.get('inter_deployment_dependencies')
        if len(dependencies) > 0 and EXTERNAL_SOURCE in dependencies[0]:
            source_deployment = None
        else:
            source_deployment = sm.get(models.Deployment, deployment_id)

        created_ids = []
        with sm.transaction():
            # Remove all previous dependencies for source_deployment
            for previous_deployment_dependency in sm.list(
                    models.InterDeploymentDependencies,
                    filters={'source_deployment': source_deployment}):
                sm.delete(previous_deployment_dependency)
            for dependency in dependencies:
                record = _create_inter_deployment_dependency(
                    source_deployment, dependency, sm)
                created_ids += [record.id]

        return ListResponse(
            items=[{'id': i} for i in created_ids],
            metadata={'pagination': {
                'total': len(created_ids),
                'size': len(created_ids),
                'offset': 0,
            }}
        )


class DeploymentGroups(SecuredResource):
    @authorize('deployment_group_list', allow_all_tenants=True)
    @rest_decorators.marshal_with(models.DeploymentGroup)
    @rest_decorators.sortable(models.DeploymentGroup)
    @rest_decorators.create_filters(models.DeploymentGroup)
    @rest_decorators.paginate
    @rest_decorators.all_tenants
    def get(self, _include=None, filters=None, pagination=None, sort=None,
            all_tenants=None):
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        return get_storage_manager().list(
            models.DeploymentGroup,
            include=_include,
            filters=filters,
            pagination=pagination,
            sort=sort,
            all_tenants=all_tenants,
            get_all_results=get_all_results
        )


class DeploymentGroupsId(SecuredResource):
    @authorize('deployment_group_get')
    @rest_decorators.marshal_with(models.DeploymentGroup)
    def get(self, group_id):
        return get_storage_manager().get(models.DeploymentGroup, group_id)

    @authorize('deployment_group_create')
    @rest_decorators.marshal_with(models.DeploymentGroup, force_get_data=True)
    @rest_decorators.not_while_cancelling
    def put(self, group_id):
        request_dict = rest_utils.get_json_and_verify_params({
            'description': {'optional': True},
            'visibility': {'optional': True},
            'labels': {'optional': True},
            'blueprint_id': {'optional': True},
            'default_inputs': {'optional': True},
            'filter_id': {'optional': True},
            'filter_rules': {'optional': True},
            'deployment_ids': {'optional': True},
            'new_deployments': {'optional': True},
            'deployments_from_group': {'optional': True},
            'creator': {'optional': True},
            'created_at': {'optional': True},
        })

        created_at = creator = None
        if request_dict.get('created_at'):
            check_user_action_allowed('set_timestamp', None, True)
            created_at = rest_utils.parse_datetime_string(
                request_dict['created_at'])

        if request_dict.get('creator'):
            check_user_action_allowed('set_owner', None, True)
            creator = rest_utils.valid_user(request_dict['creator'])

        sm = get_storage_manager()
        with sm.transaction():
            try:
                group = sm.get(models.DeploymentGroup, group_id)
            except manager_exceptions.NotFoundError:
                group = models.DeploymentGroup(id=group_id)
                sm.put(group)
            if creator:
                group.creator = creator
            if created_at:
                group.created_at = created_at
            self._set_group_attributes(sm, group, request_dict)
            changed_deps = set()
            if request_dict.get('labels') is not None:
                changed_deps |= self._set_group_labels(
                    sm,
                    group,
                    request_dict['labels']
                )
            if self._is_overriding_deployments(request_dict):
                group.deployments.clear()
            changed_deps |= self._add_group_deployments(
                sm, group, request_dict)
        self._create_new_deployments(sm, group, request_dict)
        if changed_deps:
            rm = get_resource_manager()
            rm.recalc_ancestors(changed_deps)
        return group

    def _is_overriding_deployments(self, request_dict):
        return (
            request_dict.get('deployment_ids') is not None or
            request_dict.get('filter_id') is not None or
            request_dict.get('deployments_from_group')
        )

    @authorize('deployment_group_update')
    @rest_decorators.marshal_with(models.DeploymentGroup, force_get_data=True)
    @rest_decorators.not_while_cancelling
    def patch(self, group_id):
        request_dict = rest_utils.get_json_and_verify_params({
            'add': {'optional': True},
            'remove': {'optional': True},
        })
        sm = get_storage_manager()
        with sm.transaction():
            group = sm.get(models.DeploymentGroup, group_id)
            changed_deps = set()
            if request_dict.get('add'):
                changed_deps |= self._add_group_deployments(
                    sm, group, request_dict['add']
                )
            if request_dict.get('remove'):
                self._remove_group_deployments(
                    sm, group, request_dict['remove'])
        if request_dict.get('add'):
            self._create_new_deployments(sm, group, request_dict['add'])
        if changed_deps:
            rm = get_resource_manager()
            rm.recalc_ancestors(changed_deps)
        return group

    def _delete_parents_from_deployments_group(self,
                                               sm,
                                               deployments,
                                               labels_to_delete):
        if not deployments:
            return
        rm = get_resource_manager()
        parents = rm.get_deployment_parents_from_labels(labels_to_delete)
        if not parents:
            return
        parents = sm.list(models.Deployment, filters={'id': parents})
        rm.delete_deployment_from_labels_graph(deployments, parents)
        return {p._storage_id for p in parents}

    def _set_group_attributes(self, sm, group, request_dict):
        if request_dict.get('visibility') is not None:
            group.visibility = request_dict['visibility']

        if request_dict.get('default_inputs') is not None:
            group.default_inputs = request_dict['default_inputs']

        if request_dict.get('description') is not None:
            group.description = request_dict['description']

        if request_dict.get('blueprint_id'):
            group.default_blueprint = sm.get(
                models.Blueprint, request_dict['blueprint_id'])

    def _handle_resource_counts_after_source_conversion(self,
                                                        deployments,
                                                        labels_to_create,
                                                        labels_to_delete):
        rm = get_resource_manager()
        new_types = rm.get_object_types_from_labels(labels_to_create)
        delete_types = rm.get_object_types_from_labels(labels_to_delete)
        if delete_types or new_types:
            return {d._storage_id for d in deployments}
        return set()

    def _set_group_labels(self, sm, group, raw_labels):
        rm = get_resource_manager()
        new_labels = set(rest_utils.get_labels_list(raw_labels))
        labels_to_create = rm.get_labels_to_create(group, new_labels)
        labels_to_delete = {label for label in group.labels
                            if (label.key, label.value) not in new_labels}
        _labels_to_delete = [(label.key, label.value)
                             for label in labels_to_delete]
        # Handle all created label process
        new_parents = rm.get_deployment_parents_from_labels(labels_to_create)
        changed_deps = set()
        converted_deps = self._handle_resource_counts_after_source_conversion(
            group.deployments,
            labels_to_create,
            _labels_to_delete
        )
        changed_deps |= converted_deps
        deployments, created_labels = \
            self._get_deployments_and_labels_to_add(
                sm, group.deployments, labels_to_create
            )
        if deployments and created_labels and new_parents:
            rm.add_deployment_to_labels_graph(deployments, new_parents)
            changed_deps |= {d._storage_id for d in deployments}
        self._create_deployments_labels(rm, deployments, created_labels)

        # Handle all deletion labels process
        self._delete_deployments_labels(
            sm, group.deployments, labels_to_delete)
        deleted_parents = self._delete_parents_from_deployments_group(
                sm, group.deployments, _labels_to_delete)
        if deleted_parents:
            changed_deps |= deleted_parents
        rm.create_resource_labels(
            models.DeploymentGroupLabel, group, labels_to_create)
        for label in labels_to_delete:
            sm.delete(label)
        return changed_deps

    def _get_deployments_and_labels_to_add(self,
                                           sm, deployments,
                                           labels_to_create):
        deployment_ids = [d._storage_id for d in deployments]
        target_deployments = set()
        created_labels = set()
        for key, value in labels_to_create:
            if not deployment_ids:
                existing_labels = []
            else:
                existing_labels = sm.list(models.DeploymentLabel, filters={
                    'key': key,
                    'value': value,
                    '_labeled_model_fk': deployment_ids
                }, get_all_results=True)
            skip_deployments = {
                label._labeled_model_fk for label in existing_labels
            }

            for dep in deployments:
                if dep._storage_id in skip_deployments:
                    continue
                created_labels.add((key, value))
                target_deployments.add(dep)
        return target_deployments, created_labels

    def _create_deployments_labels(self, rm, deployments, created_labels):
        """Bulk create the labels for the given deployments"""
        for dep in deployments:
            rm.create_resource_labels(
                models.DeploymentLabel, dep, created_labels)

    def _delete_deployments_labels(self, sm, deployments, labels_to_delete):
        """Bulk delete the labels for the given deployments."""
        dl_table = models.DeploymentLabel.__table__
        deployment_ids = [d._storage_id for d in deployments]
        for label in labels_to_delete:
            db.session.execute(
                dl_table.delete()
                .where(
                    sql_and(
                        dl_table.c.key == label.key,
                        dl_table.c.value == label.value,
                        dl_table.c._labeled_model_fk.in_(deployment_ids),
                    )
                )
            )

    def _get_labels_from_group(self, group):
        return [(label.key, label.value) for label in group.labels]

    def _process_labels_after_adding_deployments_to_group(self,
                                                          sm,
                                                          rm,
                                                          group,
                                                          deployments):
        group_labels = self._get_labels_from_group(group)
        _target_deployments, labels_to_add = \
            self._get_deployments_and_labels_to_add(
                sm, deployments, group_labels
            )
        # Update deployment conversion which could be from service to env or
        # vice versa
        self._handle_resource_counts_after_source_conversion(
            _target_deployments,
            labels_to_add,
            []
        )
        # Add new labels
        self._create_deployments_labels(rm, deployments, labels_to_add)

        # Add deployments to group
        for dep in deployments:
            group.deployments.append(dep)
        return labels_to_add, _target_deployments

    def _add_group_deployments(self, sm, group, request_dict):
        rm = get_resource_manager()
        deployments_to_add = set()

        deployment_ids = request_dict.get('deployment_ids')
        if deployment_ids is not None:
            deployments_to_add |= {
                sm.get(models.Deployment, dep_id) for dep_id in deployment_ids
            }

        filter_id = request_dict.get('filter_id')
        if filter_id is not None:
            deployments_to_add |= set(sm.list(
                models.Deployment,
                filter_rules=get_filter_rules_from_filter_id(
                    filter_id, models.DeploymentsFilter)
            ).items)

        filter_rules = request_dict.get('filter_rules')
        if filter_rules:
            deployments_to_add |= set(sm.list(
                models.Deployment,
                filter_rules=filter_rules).items)

        add_group = request_dict.get('deployments_from_group')
        if add_group:
            group_to_clone = sm.get(models.DeploymentGroup, add_group)
            deployments_to_add |= set(group_to_clone.deployments)

        to_update = set()
        if deployments_to_add:
            new_labels, target_deployments = \
                self._process_labels_after_adding_deployments_to_group(
                    sm, rm, group, deployments_to_add
                )

            if target_deployments and new_labels:
                parents = rm.get_deployment_parents_from_labels(new_labels)
                if parents:
                    rm.add_deployment_to_labels_graph(
                        target_deployments, parents)
                    to_update |= {d._storage_id for d in target_deployments}
        return to_update

    def _create_new_deployments(self, sm, group, request_dict):
        """Create new deployments for the group based on new_deployments"""
        rm = get_resource_manager()
        new_deployments = request_dict.get('new_deployments')
        if not new_deployments:
            return
        with sm.transaction():
            if not group.default_blueprint:
                raise manager_exceptions.ConflictError(
                    'Cannot create deployments: group {0} has no '
                    'default blueprint set'.format(group.id))
            if not all(spec.get('skip_plugins_validation')
                       for spec in new_deployments):
                rm.check_blueprint_plugins_installed(
                    group.default_blueprint.plan)
            group_labels = [(label.key, label.value) for label in group.labels]
            deployment_count = len(group.deployments)
            create_exec_group = models.ExecutionGroup(
                id=str(uuid.uuid4()),
                deployment_group=group,
                workflow_id='create_deployment_environment',
                visibility=group.visibility,
                concurrency=10,
            )
            sm.put(create_exec_group)
            self._prepare_sites(sm, new_deployments)
            for new_dep_spec in new_deployments:
                dep = self._make_new_group_deployment(
                    rm, group, new_dep_spec, deployment_count, group_labels)
                group.deployments.append(dep)
                create_exec_group.executions.append(dep.create_execution)
                deployment_count += 1
            messages = create_exec_group.start_executions(sm, rm)
        workflow_executor.execute_workflow(messages)

    def _prepare_sites(self, sm, new_deployments):
        """If new-deployment specs contain a site name, fetch those sites

        This is to only fetch the sites once, to avoid fetching them
        for each deployment separately.
        Adds the 'site' to each new_dep_spec that declared site_name.
        """
        site_names = set()
        for new_dep_spec in new_deployments:
            site_name = new_dep_spec.get('site_name')
            if site_name:
                site_names.add(site_name)

        sites = {s.name: s for s in sm.list(models.Site, filters={
            'name': list(site_names)
        }, get_all_results=True)}

        for new_dep_spec in new_deployments:
            site_name = new_dep_spec.get('site_name')
            if not site_name:
                continue
            try:
                new_dep_spec['site'] = sites[site_name]
            except KeyError:
                raise manager_exceptions.NotFoundError(
                    f'Site {site_name} does not exist'
                )

    def _make_new_group_deployment(self, rm, group, new_dep_spec, count,
                                   group_labels):
        """Create a new deployment in the group.

        The new deployment will be based on the specification given
        in the new_dep_spec dict, which can contain the keys: id, inputs,
        labels.
        """

        new_id, is_id_unique = self._new_deployment_id(group, new_dep_spec)
        inputs = new_dep_spec.get('inputs', {})
        labels = rest_utils.get_labels_list(new_dep_spec.get('labels') or [])
        labels += group_labels
        deployment_inputs = (group.default_inputs or {}).copy()
        deployment_inputs.update(inputs)
        dep = rm.create_deployment(
            blueprint=group.default_blueprint,
            deployment_id=new_id,
            private_resource=None,
            visibility=group.visibility,
            runtime_only_evaluation=new_dep_spec.get(
                'runtime_only_evaluation', False),
            site=new_dep_spec.get('site'),
        )
        group.creation_counter += 1
        dep.is_id_unique = not is_id_unique
        create_execution = dep.make_create_environment_execution(
            inputs=deployment_inputs,
            labels=labels,
            display_name=new_dep_spec.get('display_name'),
        )
        create_execution.is_id_unique = False
        return dep

    def _new_deployment_id(self, group, new_dep_spec):
        """Figure out the new deployment ID.

        Check if the ID is unique as well (if it contains a uuid): in that
        case, the uniqueness check in storage-manager isn't needed.
        Also, if there is no variable part at all, that means all deployments
        would have the same ID, and that's an error.

        :return: a pair of the deployment ID, and a boolean saying whether
            we can guarantee the ID is unique
        """
        has_variable = False
        is_unique = False
        new_id = new_dep_spec.get('id')
        if new_id:
            # provided by the user, assume the user knows what they're doing,
            # but we will still check that it's unique
            has_variable = True
        else:
            try:
                new_id = group.default_blueprint.plan[
                    'deployment_settings']['id_template']
            except KeyError:
                pass
            new_id = new_id or '{group_id}-{uuid}'

        display_name_template = new_dep_spec.get('display_name')
        if not display_name_template:
            try:
                display_name_template = group.default_blueprint.plan[
                    'deployment_settings']['display_name']
            except KeyError:
                pass

        if not isinstance(display_name_template, str):
            # it's not a string - it contains intrinsic functions - we can't
            # do anything about it here, it must be resolved in create-dep-env
            display_name_template = None

        for template, replace, makes_unique, makes_variable in [
            ('{group_id}', group.id, False, False),
            ('{uuid}', uuid.uuid4(), True, True),
            ('{blueprint_id}', group.default_blueprint.id, False, False),
            ('{count}', group.creation_counter, False, True),
            ('{site_name}', new_dep_spec.get('site_name', ''), False, False),
        ]:
            if template in new_id:
                new_id = new_id.replace(template, str(replace))
                is_unique |= makes_unique
                has_variable |= makes_variable
            if display_name_template and template in display_name_template:
                display_name_template = \
                    display_name_template.replace(template, str(replace))

        if display_name_template:
            new_dep_spec['display_name'] = display_name_template

        if not has_variable:
            raise manager_exceptions.ConflictError(
                'When creating new deployments in a group, deployment ID '
                'template must contain a variable part, eg. `{uuid}`')
        return new_id, is_unique

    def _remove_group_deployments(self, sm, group, request_dict):
        remove_ids = request_dict.get('deployment_ids') or []
        for remove_id in remove_ids:
            dep = sm.get(models.Deployment, remove_id)
            if dep in group.deployments:
                group.deployments.remove(dep)

        filter_id = request_dict.get('filter_id')
        if filter_id is not None:
            deployments = sm.list(
                models.Deployment,
                filter_rules=get_filter_rules_from_filter_id(
                    filter_id, models.DeploymentsFilter)
            )
            for dep in deployments:
                if dep in group.deployments:
                    group.deployments.remove(dep)

        filter_rules = request_dict.get('filter_rules')
        if filter_rules:
            deployments = sm.list(
                models.Deployment,
                filter_rules=filter_rules
            )
            for dep in deployments:
                if dep in group.deployments:
                    group.deployments.remove(dep)

        remove_group = request_dict.get('deployments_from_group')
        if remove_group:
            group_to_remove = sm.get(models.DeploymentGroup, remove_group)
            for dep in group_to_remove.deployments:
                if dep in group.deployments:
                    group.deployments.remove(dep)

    @authorize('deployment_group_delete')
    def delete(self, group_id):
        args = rest_utils.get_args_and_verify_arguments([
            Argument('delete_deployments', type=boolean, default=False),
            Argument('force', type=boolean, default=False),
            Argument('delete_logs', type=boolean, default=False),
        ])
        sm = get_storage_manager()
        rm = get_resource_manager()

        group = sm.get(models.DeploymentGroup, group_id)
        if args.delete_deployments:
            with sm.transaction():
                delete_exc_group = models.ExecutionGroup(
                    id=str(uuid.uuid4()),
                    workflow_id='delete_deployment_environment',
                    deployment_group=group,
                )
                sm.put(delete_exc_group)
                for dep in group.deployments:
                    rm.check_deployment_delete(dep, force=args.force)
                    delete_exc = dep.make_delete_environment_execution(
                        delete_logs=args.delete_logs
                    )
                    delete_exc_group.executions.append(delete_exc)
                messages = delete_exc_group.start_executions(sm, rm)
            workflow_executor.execute_workflow(messages)

        sm.delete(group)
        return None, 204


def _create_inter_deployment_dependency(
        source_deployment: models.Deployment,
        dependency: models.InterDeploymentDependencies,
        sm) -> models.InterDeploymentDependencies:
    now = utils.get_formatted_timestamp()

    if (TARGET_DEPLOYMENT in dependency and
            EXTERNAL_SOURCE not in dependency and
            EXTERNAL_TARGET not in dependency):
        target_deployment = sm.get(models.Deployment,
                                   dependency[TARGET_DEPLOYMENT],
                                   fail_silently=True)
    else:
        target_deployment = None

    if target_deployment:
        if target_deployment in source_deployment.get_ancestors(locking=False)\
                or target_deployment == source_deployment:
            raise manager_exceptions.ConflictError(
                f'Cyclic dependency between {source_deployment} and '
                f'{target_deployment}')

    deployment_dependency = models.InterDeploymentDependencies(
        id=str(uuid.uuid4()),
        dependency_creator=dependency[DEPENDENCY_CREATOR],
        source_deployment=source_deployment,
        target_deployment=target_deployment,
        target_deployment_func=dependency.get(TARGET_DEPLOYMENT_FUNC),
        external_source=dependency.get(EXTERNAL_SOURCE),
        external_target=dependency.get(EXTERNAL_TARGET),
        created_at=now)
    record = sm.put(deployment_dependency)
    return record

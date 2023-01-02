import pydantic
from typing import Optional

from flask import request

from manager_rest.constants import RESERVED_LABELS
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage.storage_manager import ListResult
from manager_rest.storage import models, get_storage_manager

from .. import rest_decorators, rest_utils


class _HasReserved(pydantic.BaseModel):
    reserved: Optional[bool] = pydantic.Field(
        default=False,
        alias='_reserved',
    )


class DeploymentsLabels(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('key')
    def get(self, pagination=None, search=None):
        """Get all deployments' labels' keys"""
        if _HasReserved.parse_obj(request.args).reserved:
            return ListResult.from_list(items=RESERVED_LABELS)
        return get_labels_keys(models.Deployment,
                               models.DeploymentLabel,
                               pagination,
                               search)


class DeploymentsLabelsKey(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('value')
    def get(self, key, pagination=None, search=None):
        """Get all deployments' labels' values for the specified key."""
        return get_labels_key_values(key,
                                     models.Deployment,
                                     models.DeploymentLabel,
                                     pagination,
                                     search)


class BlueprintsLabels(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('key')
    def get(self, pagination=None, search=None):
        """Get all blueprints' labels' keys"""
        if _HasReserved.parse_obj(request.args).reserved:
            return ListResult.from_list(items=RESERVED_LABELS)
        return get_labels_keys(models.Blueprint,
                               models.BlueprintLabel,
                               pagination,
                               search)


class BlueprintsLabelsKey(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('value')
    def get(self, key, pagination=None, search=None):
        """Get all blueprints' labels' values for the specified key."""
        return get_labels_key_values(key,
                                     models.Blueprint,
                                     models.BlueprintLabel,
                                     pagination,
                                     search)


def get_labels_keys(resource_model, resource_labels_model, pagination, search):
    """Get all the resource's labels' keys"""
    args = rest_utils.ListQuery.parse_obj(request.args)
    results = get_storage_manager().list(
        resource_labels_model,
        include=['key'],
        pagination=pagination,
        filters={'_labeled_model_fk': resource_model._storage_id},
        get_all_results=args.get_all_results,
        distinct=['key'],
        substr_filters=search,
        sort={'key': 'asc'}
    )

    results.items = [label.key for label in results]
    return results


def get_labels_key_values(key, resource_model, resource_labels_model,
                          pagination, search):
    """Get all resource's labels' values for the specified key."""
    rest_utils.validate_inputs({'label_key': key})
    args = rest_utils.ListQuery.parse_obj(request.args)
    results = get_storage_manager().list(
        resource_labels_model,
        include=['value'],
        pagination=pagination,
        filters={'key': key,
                 '_labeled_model_fk': resource_model._storage_id},
        get_all_results=args.get_all_results,
        distinct=['value'],
        substr_filters=search,
        sort={'value': 'asc'}
    )

    results.items = [label.value for label in results]
    return results

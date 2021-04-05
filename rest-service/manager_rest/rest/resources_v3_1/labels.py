from flask import request

from manager_rest.constants import RESERVED_LABELS
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage.storage_manager import ListResult
from manager_rest.storage import models, get_storage_manager

from .. import rest_decorators, rest_utils


class DeploymentsLabels(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('key')
    def get(self, pagination=None, search=None):
        """Get all deployments' labels' keys"""
        if _is_reserved_labels_keys_in_request():
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
        if _is_reserved_labels_keys_in_request():
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
    get_all_results = rest_utils.verify_and_convert_bool(
        '_get_all_results',
        request.args.get('_get_all_results', False)
    )
    results = get_storage_manager().list(
        resource_labels_model,
        include=['key'],
        pagination=pagination,
        filters={'_labeled_model_fk': resource_model._storage_id},
        get_all_results=get_all_results,
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
    get_all_results = rest_utils.verify_and_convert_bool(
        '_get_all_results',
        request.args.get('_get_all_results', False)
    )
    results = get_storage_manager().list(
        resource_labels_model,
        include=['value'],
        pagination=pagination,
        filters={'key': key,
                 '_labeled_model_fk': resource_model._storage_id},
        get_all_results=get_all_results,
        distinct=['value'],
        substr_filters=search,
        sort={'value': 'asc'}
    )

    results.items = [label.value for label in results]
    return results


def _is_reserved_labels_keys_in_request():
    return rest_utils.verify_and_convert_bool(
        'reserved', request.args.get('_reserved', False))

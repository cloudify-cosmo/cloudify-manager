from flask import request

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager

from .. import rest_decorators, rest_utils


class DeploymentsLabels(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('key')
    def get(self, pagination=None, search=None):
        """Get all deployments' labels' keys in the current tenant"""
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        results = get_storage_manager().list(
            models.DeploymentLabel,
            include=['key'],
            pagination=pagination,
            filters={'_labeled_model_fk': models.Deployment._storage_id},
            get_all_results=get_all_results,
            distinct=['key'],
            substr_filters=search,
            sort={'key': 'asc'}
        )

        results.items = [label.key for label in results]
        return results


class DeploymentsLabelsKey(SecuredResource):
    @authorize('labels_list')
    @rest_decorators.marshal_list_response
    @rest_decorators.paginate
    @rest_decorators.search('value')
    def get(self, key, pagination=None, search=None):
        """Get all deployments' labels' values for the specified key."""
        rest_utils.validate_inputs({'label_key': key})
        get_all_results = rest_utils.verify_and_convert_bool(
            '_get_all_results',
            request.args.get('_get_all_results', False)
        )
        results = get_storage_manager().list(
            models.DeploymentLabel,
            include=['value'],
            pagination=pagination,
            filters={'key': key,
                     '_labeled_model_fk': models.Deployment._storage_id},
            get_all_results=get_all_results,
            distinct=['value'],
            substr_filters=search,
            sort={'value': 'asc'}
        )

        results.items = [label.value for label in results]
        return results

from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import models, get_storage_manager


class DeploymentsLabels(SecuredResource):

    @authorize('labels_keys_list')
    def get(self):
        """Get all deployments labels' keys"""
        raw_labels_list = get_storage_manager().list(models.DeploymentLabel,
                                                     include=['key'],
                                                     get_all_results=True)
        keys_list = list(set(label.key for label in raw_labels_list))
        return {'metadata': {}, 'items': keys_list}

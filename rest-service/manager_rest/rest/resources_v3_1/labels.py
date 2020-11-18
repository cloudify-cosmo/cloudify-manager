from manager_rest import utils
from manager_rest.storage import models
from manager_rest.storage.models_base import db
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize


class DeploymentsLabels(SecuredResource):

    @authorize('labels_list')
    def get(self):
        """Get all deployments labels' keys"""
        current_tenant = utils.current_tenant._get_current_object()
        results = (db.session.query(models.DeploymentLabel.key)
                   .join(models.Deployment)
                   .filter(models.Deployment._tenant_id == current_tenant.id)
                   .distinct()
                   .all())

        keys_list = [result.key for result in results]
        return {'metadata': {}, 'items': keys_list}

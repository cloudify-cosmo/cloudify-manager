from flask_restful_swagger import swagger

from manager_rest.rest import rest_decorators
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (get_storage_manager,
                                  models)
from manager_rest.storage.storage_manager import ListResult


class Workflows(SecuredResource):
    @swagger.operation(
        responseClass='List[dict]',
        nickname="list",
        notes="Returns a list of defined workflows."
    )
    @rest_decorators.marshal_list_response
    @authorize('deployment_list')
    def get(self, **kwargs):
        """
        List workflows defined for deployments filtered by kwargs.
        """
        workflows = []
        for dep in get_storage_manager().list(models.Deployment,
                                              include=['id', 'workflows'],
                                              get_all_results=True):
            workflows += models.Deployment._list_workflows(dep.workflows)

        return ListResult([w.as_dict() for w in workflows],
                          {'pagination': {
                              'total': len(workflows),
                              'size': len(workflows),
                              'offset': 0,
                          }}
        )

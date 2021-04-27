import typing

from flask_restful_swagger import swagger

from manager_rest.rest import filters_utils, rest_decorators, rest_utils
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (get_storage_manager,
                                  models)

from ..responses_v2 import ListResponse

if typing.TYPE_CHECKING:
    from typing import List, Iterable
    from manager_rest.rest.responses import Workflow


class Workflows(SecuredResource):
    @swagger.operation(
        responseClass='List[dict]',
        nickname="list",
        notes="Returns a list of defined workflows."
    )
    @rest_decorators.marshal_list_response
    @rest_decorators.create_filters(models.Deployment)
    @rest_decorators.search('id')
    @rest_decorators.filter_id
    @authorize('deployment_list')
    def get(self, filters=None, search=None, filter_id=None, **kwargs):
        """
        List workflows defined for deployments filtered by kwargs.
        """
        _include = ['id', 'workflows']
        filters, _include = rest_utils.modify_deployments_list_args(filters,
                                                                    _include)
        filter_rules = filters_utils.get_filter_rules_from_filter_id(
            filter_id, models.DeploymentsFilter)
        result = get_storage_manager().list(
            models.Deployment,
            include=_include,
            filters=filters,
            substr_filters=search,
            get_all_results=True,
            filter_rules=filter_rules,
            distinct=['_blueprint_fk'],
        )

        return workflows_list_response(result)


def workflows_list_response(deployments: 'Iterable') -> ListResponse:
    workflows = _extract_workflows(deployments)
    pagination = {
        'total': len(workflows),
        'size': len(workflows),
        'offset': 0,
    }
    return ListResponse(items=[w.as_dict() for w in workflows],
                        metadata={'pagination': pagination})


def _extract_workflows(
        deployments: 'List[models.Deployment]') -> 'List[Workflow]':
    workflows = set()
    for dep in deployments:
        workflows |= set(models.Deployment._list_workflows(dep.workflows))
    return list(workflows)


def _merge_workflows(w1: 'List[Workflow]',
                     w2: 'List[Workflow]') -> 'List[Workflow]':
    workflows = {}
    for w in w1 + w2:
        workflows[w.name] = w
    return list(workflows.values())

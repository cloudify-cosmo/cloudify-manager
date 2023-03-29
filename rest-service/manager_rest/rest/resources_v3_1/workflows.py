from typing import Iterable, List

from manager_rest.rest import (
    filters_utils,
    rest_decorators,
    rest_utils,
    swagger,
)
from manager_rest.security import SecuredResource
from manager_rest.security.authorization import authorize
from manager_rest.storage import (get_storage_manager,
                                  models)

from manager_rest.rest.responses import Workflow
from manager_rest.rest.responses_v2 import ListResponse


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
        filters = filters or {}
        filters.update(rest_utils.deployment_group_id_filter())
        sm = get_storage_manager()
        filter_rules = filters_utils.get_filter_rules_from_filter_id(
            sm, filter_id, models.DeploymentsFilter)
        result = sm.list(
            models.Deployment,
            include=_include,
            filters=filters,
            substr_filters=search,
            get_all_results=True,
            filter_rules=filter_rules,
            distinct=['_blueprint_fk'],
        )

        return workflows_list_response(result)


def workflows_list_response(
        deployments: Iterable[models.Deployment],
        common_only: bool = False,
) -> ListResponse:
    workflows = _extract_workflows(deployments, common_only=common_only)
    pagination = {
        'total': len(workflows),
        'size': len(workflows),
        'offset': 0,
    }
    return ListResponse(items=[w.as_dict() for w in workflows],
                        metadata={'pagination': pagination})


def _extract_workflows(
        deployments: Iterable[models.Deployment],
        common_only: bool = False,
) -> List[Workflow]:
    if not deployments:
        return []
    first_dep, *deployments = deployments
    workflows = set(first_dep._list_workflows())
    for dep in deployments:
        if common_only:
            workflows &= set(dep._list_workflows())
        else:
            workflows |= set(dep._list_workflows())
    return list(workflows)


def _merge_workflows(w1: List[Workflow], w2: List[Workflow]) -> List[Workflow]:
    workflows = {}
    for w in w1 + w2:
        workflows[w.name] = w
    return list(workflows.values())

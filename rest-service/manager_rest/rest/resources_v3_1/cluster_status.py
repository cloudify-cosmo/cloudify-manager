import os

from flask import request

from cloudify.cluster_status import ServiceStatus

from manager_rest.rest import responses, swagger
from manager_rest.security.authorization import authorize
from manager_rest.rest.rest_decorators import marshal_with
from manager_rest.security import SecuredResource
from manager_rest.cluster_status_manager import (
    get_cluster_status as get_cluster_status_legacy,
)
from manager_rest.cluster_status_utils import STATUS, get_cluster_status
from manager_rest.rest.rest_utils import (verify_and_convert_bool,
                                          get_json_and_verify_params)


class ClusterStatus(SecuredResource):
    @staticmethod
    def _get_request_dict():
        request_dict = get_json_and_verify_params({
            'reporting_freq': {'type': int},
            'report': {'type': dict},
            'timestamp': {'type': str}
        })
        return request_dict

    @swagger.operation(
        responseClass=responses.Status,
        nickname="cluster-status",
        notes="Returns state of the Cloudify cluster"
    )
    @authorize('cluster_status_get')
    @marshal_with(responses.Status)
    def get(self):
        """Get the status of the entire cloudify cluster"""
        summary_response = verify_and_convert_bool(
            'summary',
            request.args.get('summary', False)
        )
        if os.environ.get('RUNTIME_ENVIRONMENT', 'legacy').lower() in [
            'k8s',
            'kubernetes',
        ]:
            status = get_cluster_status()
        else:
            status = get_cluster_status_legacy(detailed=not summary_response)

        # If the response should be only the summary
        if summary_response:
            short_status = status.get(STATUS)
            status_code = 500 if short_status == ServiceStatus.FAIL else 200
            return {'status': short_status, 'services': {}}, status_code

        return status

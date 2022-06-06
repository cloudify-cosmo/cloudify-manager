#!/opt/manager/env/bin/python

import os
from datetime import datetime

from manager_rest import constants
from manager_rest.storage import models
from manager_rest.storage.models_base import db
from manager_rest.flask_utils import setup_flask_app


def create_system_filters():
    with setup_flask_app().app_context():
        current_deployment_filters = db.session.query(models.DeploymentsFilter)
        curr_dep_filters_ids = {dep_filter.id for dep_filter
                                in current_deployment_filters}
        creator = models.User.query.get(constants.BOOTSTRAP_ADMIN_ID)
        tenant = models.Tenant.query.get(constants.DEFAULT_TENANT_ID)
        now = datetime.utcnow()
        if 'csys-environment-filter' not in curr_dep_filters_ids:
            env_filter = {
                'id': 'csys-environment-filter',
                'value': [
                    {
                        'key': 'csys-obj-type',
                        'values': ['environment'],
                        'operator': 'any_of',
                        'type': 'label'
                    },
                    {
                        'key': 'csys-obj-parent',
                        'values': [],
                        'operator': 'is_null',
                        'type': 'label'
                    }
                ]
            }
            _add_deployments_filter(env_filter, creator, tenant, now)
        if 'csys-service-filter' not in curr_dep_filters_ids:
            service_filter = {
                'id': 'csys-service-filter',
                'value': [
                    {
                        'key': 'csys-obj-type',
                        'values': ['environment'],
                        'operator': 'is_not',
                        'type': 'label'
                    }
                ]
            }
            _add_deployments_filter(service_filter, creator, tenant, now)

        for filter_id, obj_type_value in {
            'csys-k8s-filter': 'k8s',
            'csys-terraform-filter': 'terraform',
            'aws-deployments': 'aws',
            'azure-deployments': 'azure',
            'gcp-deployments': 'gcp',
            'terragrunt-deployments': 'terragrunt',
            'helm-deployments': 'helm',
            'ansible-deployments': 'ansible',
            'starlingx-deployments': 'starlingx',
            'vsphere-deployments': 'vsphere',
            'docker-deployments': 'docker',
            'netconf-deployments': 'netconf',
            'fabric-deployments': 'fabric',
            'libvirt-deployments': 'libvirt',
            'utilities-deployments': 'utilities',
            'host-pool-deployments': 'host-pool',
            'diamond-deployments': 'diamond',
            'openstack-deployments': 'openstack',
            'openstack-v3-deployments': 'openstack-v3',
            'vcloud-deployments': 'vcloud',
        }.items():
            if filter_id in curr_dep_filters_ids:
                continue
            service_filter = {
                'id': filter_id,
                'value': [
                    {
                        'key': 'obj-type',
                        'values': [obj_type_value],
                        'operator': 'any_of',
                        'type': 'label',
                    }
                ]
            }
            _add_deployments_filter(service_filter, creator, tenant, now)

        db.session.commit()


def _add_deployments_filter(sys_filter_dict, creator, tenant, now):
    sys_filter_dict['created_at'] = now
    sys_filter_dict['updated_at'] = now
    sys_filter_dict['visibility'] = 'global'
    sys_filter_dict['is_system_filter'] = True
    sys_filter_dict['creator'] = creator
    sys_filter_dict['tenant'] = tenant
    db.session.add(models.DeploymentsFilter(**sys_filter_dict))


def _add_blueprints_filter(sys_filter_dict, creator, tenant, now):
    sys_filter_dict['created_at'] = now
    sys_filter_dict['updated_at'] = now
    sys_filter_dict['visibility'] = 'global'
    sys_filter_dict['is_system_filter'] = True
    sys_filter_dict['creator'] = creator
    sys_filter_dict['tenant'] = tenant
    db.session.add(models.BlueprintsFilter(**sys_filter_dict))


if __name__ == '__main__':
    if 'MANAGER_REST_CONFIG_PATH' not in os.environ:
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            "/opt/manager/cloudify-rest.conf"
    create_system_filters()

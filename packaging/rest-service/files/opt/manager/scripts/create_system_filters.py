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
        if ({'csys-environment-filter', 'csys-service-filter'} ==
                curr_dep_filters_ids):
            # System filters already exist
            return
        now = datetime.utcnow()
        creator = db.session.query(models.User).filter_by(
            id=constants.BOOTSTRAP_ADMIN_ID).first()
        tenant = db.session.query(models.Tenant).filter_by(
            id=constants.DEFAULT_TENANT_ID).first()
        system_filters = [
            {
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
            },
            {
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
        ]
        for sys_filter in system_filters:
            sys_filter['created_at'] = now
            sys_filter['updated_at'] = now
            sys_filter['visibility'] = 'global'
            sys_filter['is_system_filter'] = True
            sys_filter['creator'] = creator
            sys_filter['tenant'] = tenant
            db.session.add(models.DeploymentsFilter(**sys_filter))

        db.session.commit()


if __name__ == '__main__':
    if 'MANAGER_REST_CONFIG_PATH' not in os.environ:
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            "/opt/manager/cloudify-rest.conf"
    create_system_filters()

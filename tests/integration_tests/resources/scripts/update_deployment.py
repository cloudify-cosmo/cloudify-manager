import os
import argparse

from manager_rest import config, storage
from manager_rest.flask_utils import setup_flask_app


def main(deployment_id):
    # We need to set the environment variable for rest config path as its
    # only available on the context of restservice
    os.environ['MANAGER_REST_CONFIG_PATH'] = '/opt/manager/cloudify-rest.conf'
    setup_flask_app()
    config.instance.load_configuration(from_db=False)
    sm = storage.get_storage_manager()
    dep = sm.get(storage.models.Deployment, deployment_id)
    dep.inputs['input1'] = 'bbb'
    dep.inputs['fail_create'] = False
    sm.update(dep, modified_attrs=['inputs'])
    for node in dep.nodes:
        node.properties['prop2'] = 'bbb'
        sm.update(node, modified_attrs=['properties'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--deployment-id', dest='deployment_id')
    args = parser.parse_args()
    main(**vars(args))

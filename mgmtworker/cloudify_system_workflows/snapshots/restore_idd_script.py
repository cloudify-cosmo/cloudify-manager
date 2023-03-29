import sys
import json
import uuid
import queue
import logging
import threading

from os.path import join

from contextlib import contextmanager
from logging.handlers import WatchedFileHandler

from manager_rest import utils
from manager_rest import config
from manager_rest.rest import rest_utils
from manager_rest.storage import models
from manager_rest.storage.storage_manager import SQLStorageManager
from manager_rest.constants import FILE_SERVER_BLUEPRINTS_FOLDER
from manager_rest.flask_utils import (
    setup_flask_app,
    get_tenant_by_name,
    set_tenant_in_app,
)
from manager_rest.rest.search_utils import GetValuesWithStorageManager

from cloudify.constants import SHARED_RESOURCE, COMPONENT
from cloudify.deployment_dependencies import format_dependency_creator

LOGFILE = '/var/log/cloudify/mgmtworker/logs/restore_idd.log'

logger = logging.getLogger('mgmtworker')
logger.setLevel(logging.INFO)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                  '[%(name)s] %(message)s',
                              datefmt='%d/%m/%Y %H:%M:%S')
file_handler = WatchedFileHandler(filename=LOGFILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

COMPONENT_TYPE = 'cloudify.nodes.Component'
SHARED_RESOURCE_TYPE = 'cloudify.nodes.SharedResource'
SERVICE_COMPONENT_TYPE = 'cloudify.nodes.ServiceComponent'
SERVICE_COMPOSITION_TYPES = [COMPONENT_TYPE,
                             SERVICE_COMPONENT_TYPE,
                             SHARED_RESOURCE_TYPE]
EXTERNAL_SOURCE = 'external_source'
EXTERNAL_TARGET = 'external_target'
NUM_THREADS = 15


@contextmanager
def get_storage_manager_instance():
    """Configure and yield a storage_manager instance.
    This is to be used only OUTSIDE of the context of the REST API.
    """
    try:
        app = setup_flask_app()
        with app.app_context():
            config.instance.load_configuration()
            sm = SQLStorageManager(user=models.User.query.get(0))
            yield sm
    finally:
        config.reset(config.Config())


def is_capable_for_idd(blueprint_plan):
    for i in blueprint_plan['nodes']:
        if i['type'] in SERVICE_COMPOSITION_TYPES:
            return True
    if 'get_capability' in json.dumps(blueprint_plan['nodes']):
        return True
    if 'get_capability' in json.dumps(blueprint_plan['outputs']):
        return True
    if 'get_capability' in json.dumps(blueprint_plan['relationships']):
        return True
    if 'get_capability' in json.dumps(blueprint_plan['workflows']):
        return True
    return False


def create_inter_deployment_dependencies(deployments_queue,
                                         failed_deployments_queue,
                                         update_service_composition,
                                         tenant_name):
    while True:
        try:
            deployment_id, deployment_tenant = deployments_queue.get_nowait()
        except queue.Empty:
            break

        try:
            restore_inter_deployment_dependencies(deployment_id,
                                                  update_service_composition,
                                                  tenant_name)
        except RuntimeError as err:
            failed_deployments_queue.put((deployment_id, deployment_tenant))
            logger.info('Failed creating inter deployment '
                        'dependencies for deployment %s from '
                        'tenant %s. %s',
                        deployment_id, deployment_tenant, err)
        deployments_queue.task_done()


def restore_inter_deployment_dependencies(deployment_id,
                                          update_service_composition,
                                          tenant_name):
    with get_storage_manager_instance() as sm:
        set_tenant_in_app(get_tenant_by_name(tenant_name))
        deployment = sm.get(models.Deployment, deployment_id)
        blueprint = deployment.blueprint
        app_dir = join(FILE_SERVER_BLUEPRINTS_FOLDER,
                       utils.current_tenant.name,
                       blueprint.id)
        app_blueprint = blueprint.main_file_name
        logger.info('{0}: BP in {1}/{2}'.format(deployment_id,
                                                app_dir,
                                                app_blueprint))

        parsed_deployment = rest_utils.get_parsed_deployment(
            blueprint, app_dir, app_blueprint)
        deployment_plan = rest_utils.get_deployment_plan(
            parsed_deployment, deployment.inputs,
            values_getter=GetValuesWithStorageManager(sm, deployment_id))
        logger.info('{0}: Parsed plan'.format(deployment.id))

        rest_utils.update_deployment_dependencies_from_plan(
            deployment.id, deployment_plan, sm, lambda *_: True)
        logger.info('{0}: Updated dependencies from plan'.format(
            deployment.id))

        if update_service_composition:
            create_service_composition_dependencies(deployment_plan,
                                                    deployment,
                                                    sm)


def create_service_composition_dependencies(deployment_plan, deployment, sm):
    for node in deployment_plan['nodes']:
        node_type = node.get('type')
        if node_type in (COMPONENT_TYPE, SHARED_RESOURCE_TYPE):

            logger.info('{0}.{1}: creating service composition deps'.format(
                deployment.id, node['id']))
            prefix = (COMPONENT if node_type == COMPONENT_TYPE
                      else SHARED_RESOURCE)

            instances = sm.list(
                models.NodeInstance,
                filters={'node_id': node['id'],
                         'deployment_id': deployment.id},
                get_all_results=True
            )
            for instance in instances:
                target_deployment_id =\
                    instance.runtime_properties['deployment']['id']
                suffix = instance.id
                target_deployment = None
                if target_deployment_id:
                    target_deployment = sm.get(models.Deployment,
                                               target_deployment_id,
                                               all_tenants=True)
                dependency_creator = format_dependency_creator(prefix,
                                                               suffix)
                put_deployment_dependency(deployment,
                                          target_deployment,
                                          dependency_creator,
                                          sm)


def put_deployment_dependency(source_deployment, target_deployment,
                              dependency_creator, sm):
    now = utils.get_formatted_timestamp()
    deployment_dependency = models.InterDeploymentDependencies(
        id=str(uuid.uuid4()),
        dependency_creator=dependency_creator,
        source_deployment=source_deployment,
        target_deployment=target_deployment,
        created_at=now)
    sm.put(deployment_dependency)


def main():
    tenant_name = sys.argv[1]
    update_service_composition = (sys.argv[2] == 'True')
    with get_storage_manager_instance() as sm:
        set_tenant_in_app(get_tenant_by_name(tenant_name))

        blueprints = sm.list(models.Blueprint)
        idd_capable_blueprints = []

        for bp in blueprints:
            if is_capable_for_idd(bp.plan):
                idd_capable_blueprints.append(bp.id)
        logger.info('IDD capable blueprints: {0}'.format(
            idd_capable_blueprints))
        if not idd_capable_blueprints:
            return

        deployments = sm.list(
            models.Deployment,
            filters={'blueprint_id': idd_capable_blueprints})

        deployments_queue = queue.Queue()
        failed_deployments_queue = queue.Queue()
        for dep in deployments:
            deployments_queue.put((dep.id, dep.tenant.name))

        logger.info('IDD capable deployments: {0}'.format(
            [dep.id for dep in deployments]))

    for i in range(min(NUM_THREADS, deployments_queue.qsize())):
        t = threading.Thread(
            target=create_inter_deployment_dependencies,
            args=(deployments_queue,
                  failed_deployments_queue,
                  update_service_composition,
                  tenant_name)
        )
        t.start()
    deployments_queue.join()

    if not failed_deployments_queue.empty():
        deployments = list(failed_deployments_queue.queue)
        logger.critical('Failed create the inter deployment '
                        'dependencies from the following '
                        'deployments {0}. See exception '
                        'tracebacks logged above for more '
                        'details'.format(deployments))
        exit(1)


if __name__ == '__main__':
    main()

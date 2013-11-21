__author__ = 'dan'

import resources
from file_server import FileServer
from flask import Flask
from flask.ext.restful import Api
import tempfile
from blueprints_manager import BlueprintsManager
from os import path
import shutil
import argparse

app = Flask(__name__)
api = Api(app)

file_server = None
blueprints_manager = None

api.add_resource(resources.Blueprints, '/blueprints')
api.add_resource(resources.BlueprintsId, '/blueprints/<string:blueprint_id>')
api.add_resource(resources.BlueprintsIdExecutions, '/blueprints/<string:blueprint_id>/executions')


def copy_resources():
    file_server_root = app.config['FILE_SERVER_ROOT']

    # build orchestrator dir
    orchestrator_resources = path.abspath(__file__)
    for i in range(3):
        orchestrator_resources = path.dirname(orchestrator_resources)
    orchestrator_resources = path.join(orchestrator_resources, 'orchestrator/src/main/resources')

    # resources for dsl parser
    cloudify_resources = path.join(orchestrator_resources, 'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root, 'cloudify'))

    alias_mapping_resource = path.join(orchestrator_resources, 'org/cloudifysource/cosmo/dsl/alias-mappings.yaml')
    shutil.copy(alias_mapping_resource, path.join(file_server_root, 'cloudify/alias-mappings.yaml'))


def stop_file_server():
    global file_server
    if file_server is not None:
        file_server.stop()


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port',
        help='The port to start the rest server in',
        default=8100,
        type=int
    )
    parser.add_argument(
        '--workflow_service_base_uri',
        help='Workflow service base URI'
    )
    return parser.parse_args()


class TestArgs(object):
    workflow_service_base_uri = None


def main():
    if app.config['Testing']:
        args = TestArgs()
    else:
        args = parse_arguments()

    if args.workflow_service_base_uri is not None:
        workflow_service_base_uri = args.workflow_service_base_uri
        if workflow_service_base_uri.endswith('/'):
            workflow_service_base_uri = workflow_service_base_uri[0:-1]
        app.config['WORKFLOW_SERVICE_BASE_URI'] = workflow_service_base_uri

    file_server_root = tempfile.mkdtemp()
    app.config['FILE_SERVER_ROOT'] = file_server_root

    global blueprints_manager
    blueprints_manager = BlueprintsManager()

    global file_server
    file_server = FileServer(file_server_root)
    file_server.start()

    copy_resources()

    if not app.config['Testing']:
        app.run(host='0.0.0.0', port=args.port)

if __name__ == '__main__':
    app.config['Testing'] = False
    main()

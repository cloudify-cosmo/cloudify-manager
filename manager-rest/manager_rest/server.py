__author__ = 'dan'

import config
import resources
from file_server import FileServer
from flask import Flask
from flask.ext.restful import Api
import tempfile
from os import path
import shutil
import argparse
import signal
import sys
import logging
import blueprints_manager
import events_manager

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(logging.StreamHandler(sys.stdout))

api = Api(app)
resources.setup_resources(api)

file_server = None


def copy_resources():
    file_server_root = config.instance().file_server_root

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


def setup_shutdown_hook():
    #TODO this handler is called twice which in turn leads to an exception thrown during the file server shutdown
    def handle(*_):
        stop_file_server()
        sys.exit()
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
        signal.signal(sig, handle)


def stop_file_server():
    global file_server
    if file_server is not None:
        file_server.stop()
        file_server = None


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
    parser.add_argument(
        '--events_files_path',
        help='Path where event files are stored (the file\'s content will be served using the events api)',
        default=None
    )
    return parser.parse_args()


def reset_state(configuration=None):
    config.reset(configuration)
    blueprints_manager.reset()
    events_manager.reset()


def main():
    if app.config['Testing']:
        class TestArgs(object):
            workflow_service_base_uri = None
            events_files_path = None
        args = TestArgs()
    else:
        args = parse_arguments()

    if args.workflow_service_base_uri is not None:
        workflow_service_base_uri = args.workflow_service_base_uri
        if workflow_service_base_uri.endswith('/'):
            workflow_service_base_uri = workflow_service_base_uri[0:-1]
        config.instance().workflow_service_base_uri = workflow_service_base_uri

    if args.events_files_path is not None:
        config.instance().events_files_path = args.events_files_path
        # TODO: create manager with configuration - this is just a temporary hack.
        events_manager.instance().set_events_path(args.events_files_path)

    file_server_root = tempfile.mkdtemp()
    config.instance().file_server_root = file_server_root

    global file_server
    file_server = FileServer(file_server_root)
    file_server.start()

    copy_resources()

    if not app.config['Testing']:
        app.run(host='0.0.0.0', port=args.port)

if __name__ == '__main__':
    setup_shutdown_hook()
    app.config['Testing'] = False
    config.instance().test_mode = False
    main()

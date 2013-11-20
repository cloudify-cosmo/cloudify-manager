__author__ = 'dan'

import resources
from file_server import FileServer
from flask import Flask
from flask.ext.restful import Api
import tempfile
from blueprints_manager import BlueprintsManager
from os import path
import shutil

app = Flask(__name__)
api = Api(app)

file_server = None
blueprints_manager = BlueprintsManager()

api.add_resource(resources.Blueprints, '/blueprints')
api.add_resource(resources.BlueprintsId, '/blueprints/<string:blueprint_id>')


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



def main():
    file_server_root = tempfile.mkdtemp()
    app.config['FILE_SERVER_ROOT'] = file_server_root
    global file_server
    file_server = FileServer(file_server_root)
    file_server.start()
    copy_resources()
    if __name__ == '__main__':
        app.run()

if __name__ == '__main__':
    main()

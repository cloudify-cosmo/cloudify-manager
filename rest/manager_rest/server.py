__author__ = 'dan'

import responses
from file_server import FileServer, PORT as file_server_port
from flask import Flask, request
from flask.ext.restful import Api, Resource, abort, marshal_with
import tempfile
from blueprints_manager import BlueprintsManager
from os import path
import shutil
import tarfile

app = Flask(__name__)
api = Api(app)

file_server_root = tempfile.mkdtemp()
file_server = FileServer(file_server_root)

blueprints_manager = BlueprintsManager()


def verify_json_content_type():
    if request.content_type != 'application/json':
        abort(415)


class BaseResource(Resource):

    def post_impl(self):
        raise NotImplemented('Deriving class should implement this method')

    # should all location header
    def post(self):
        verify_json_content_type()
        result = self.post_impl()
        return result, 201

    def put_impl(self):
        raise NotImplemented('Deriving class should implement this method')

    def put(self):
        verify_json_content_type()
        result = self.put_impl()
        return result

    def patch_impl(self):
        raise NotImplemented('Deriving class should implement this method')

    def patch(self):
        verify_json_content_type()
        result = self.patch_impl()
        return result


class Blueprints(BaseResource):

    def get(self):
        return blueprints_manager.blueprints

    @marshal_with(responses.BlueprintState.resource_fields)
    def post(self):
        # save uploaded file
        uploaded_file = request.files['application_archive']
        archive_target_path = path.join(file_server_root, uploaded_file.filename)
        uploaded_file.save(archive_target_path)

        # extract application to file server
        tar = tarfile.open(archive_target_path)
        tar.extractall(file_server_root)

        file_server_base_url = 'http://localhost:{0}'.format(file_server_port)
        dsl_path = '{0}/{1}'.format(file_server_base_url, request.form['application_file'])
        alias_mapping = '{0}/{1}'.format(file_server_base_url, 'cloudify/alias-mappings.yaml')
        resources_base = file_server_base_url + '/'

        # add to blueprints manager (will also dsl_parse it)
        return blueprints_manager.publish(dsl_path, alias_mapping, resources_base), 201


api.add_resource(Blueprints, '/blueprints')


def copy_resources():

    # build orchestrator dir
    orchestrator_resources = __file__
    for i in range(3):
        orchestrator_resources = path.dirname(orchestrator_resources)
    orchestrator_resources = path.join(orchestrator_resources, 'orchestrator/src/main/resources')

    # resources for dsl parser
    cloudify_resources = path.join(orchestrator_resources, 'cloudify')
    shutil.copytree(cloudify_resources, path.join(file_server_root, 'cloudify'))

    alias_mapping_resource = path.join(orchestrator_resources, 'org/cloudifysource/cosmo/dsl/alias-mappings.yaml')
    shutil.copy(alias_mapping_resource, path.join(file_server_root, 'cloudify/alias-mappings.yaml'))


def stop_file_server():
    file_server.stop()


def main():
    file_server.start()
    copy_resources()
    if __name__ == '__main__':
        app.run(debug=True)

if __name__ == '__main__':
    main()

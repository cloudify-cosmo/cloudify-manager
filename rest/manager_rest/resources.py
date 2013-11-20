__author__ = 'dan'

from file_server import PORT as file_server_port

from flask import request
from flask.ext.restful import Resource, abort, marshal_with, marshal
from os import path
import responses
import tarfile


def blueprints_manager():
    from server import blueprints_manager
    return blueprints_manager


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
        return [marshal(blueprint, responses.BlueprintState.resource_fields) for
                blueprint in blueprints_manager().blueprints_list()]

    @marshal_with(responses.BlueprintState.resource_fields)
    def post(self):
        from server import app
        file_server_root = app.config['FILE_SERVER_ROOT']

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
        return blueprints_manager().publish(dsl_path, alias_mapping, resources_base), 201


class BlueprintsId(BaseResource):

    @marshal_with(responses.BlueprintState.resource_fields)
    def get(self, blueprint_id):
        return blueprints_manager().get_blueprint(blueprint_id)


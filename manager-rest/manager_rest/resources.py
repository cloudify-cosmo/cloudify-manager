__author__ = 'dan'

from file_server import PORT as file_server_port
import config

from flask import request
from flask.ext.restful import Resource, abort, marshal_with, marshal
from os import path
import responses
import tarfile


def blueprints_manager():
    import blueprints_manager
    return blueprints_manager.instance()


def verify_json_content_type():
    if request.content_type != 'application/json':
        abort(415)


def setup_resources(api):
    api.add_resource(Blueprints, '/blueprints')
    api.add_resource(BlueprintsId, '/blueprints/<string:blueprint_id>')
    api.add_resource(BlueprintsIdExecutions, '/blueprints/<string:blueprint_id>/executions')
    api.add_resource(ExecutionsId, '/executions/<string:execution_id>')
    api.add_resource(BlueprintsIdValidate, '/blueprints/<string:blueprint_id>/validate')


class Blueprints(Resource):

    def get(self):
        return [marshal(blueprint, responses.BlueprintState.resource_fields) for
                blueprint in blueprints_manager().blueprints_list()]

    @marshal_with(responses.BlueprintState.resource_fields)
    def post(self):
        file_server_root = config.instance().file_server_root

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
        return blueprints_manager().publish_blueprint(dsl_path, alias_mapping, resources_base), 201


class BlueprintsId(Resource):

    @marshal_with(responses.BlueprintState.resource_fields)
    def get(self, blueprint_id):
        return blueprints_manager().get_blueprint(blueprint_id)


class BlueprintsIdValidate(Resource):

    @marshal_with(responses.BlueprintValidationStatus.resource_fields)
    def get(self, blueprint_id):
        return blueprints_manager().validate_blueprint(blueprint_id)


class BlueprintsIdExecutions(Resource):

    def get(self, blueprint_id):
        return [marshal(execution, responses.Execution.resource_fields) for
                execution in blueprints_manager().get_blueprint(blueprint_id).executions_list()]

    @marshal_with(responses.Execution.resource_fields)
    def post(self, blueprint_id):
        verify_json_content_type()
        workflow_id = request.json['workflowId']
        return blueprints_manager().execute_workflow(blueprint_id, workflow_id), 201


class ExecutionsId(Resource):

    @marshal_with(responses.Execution.resource_fields)
    def get(self, execution_id):
        return blueprints_manager().get_workflow_state(execution_id)

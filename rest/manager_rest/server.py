__author__ = 'dan'

from flask import Flask, request
from flask.ext.restful import Api, Resource, abort

app = Flask(__name__)
api = Api(app)


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
        return {'hello': 'world'}

    def post_impl(self):
        return {'hello': 'world'}

api.add_resource(Blueprints, '/blueprints')

if __name__ == '__main__':
    app.run(debug=True)

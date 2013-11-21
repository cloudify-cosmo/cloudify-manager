__author__ = 'dan'


from base_test import BaseServerTestCase
import tempfile
import os
import tarfile


class BlueprintsTestCase(BaseServerTestCase):

    def post_blueprint_args(self):
        def make_tarfile(output_filename, source_dir):
            with tarfile.open(output_filename, "w:gz") as tar:
                tar.add(source_dir, arcname=os.path.basename(source_dir))

        def tar_mock_blueprint():
            tar_path = tempfile.mktemp()
            source_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mock_blueprint')
            make_tarfile(tar_path, source_dir)
            return tar_path

        return [
            '/blueprints',
            tar_mock_blueprint(),
            'application_archive',
            'mezzanine-app.tar.gz',
            {'application_file': 'mock_blueprint/mezzanine_blueprint.yaml'}
        ]

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_post_and_then_get(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args()).json
        self.assertEquals('mezzanine', post_blueprints_response['name'])
        get_blueprints_response = self.get('/blueprints').json
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args()).json
        get_blueprint_by_id_response = self.get('/blueprints/{0}'.format(post_blueprints_response['id'])).json
        self.assertEquals(post_blueprints_response, get_blueprint_by_id_response)

    def test_post_blueprints_id_executions(self):
        blueprint = self.post_file(*self.post_blueprint_args()).json
        execution = self.post('/blueprints/{0}/executions'.format(blueprint['id']), {
            'workflowId': 'install'
        }).json
        self.assertEquals(execution['workflowId'], 'install')
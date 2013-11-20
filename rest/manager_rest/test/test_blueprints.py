__author__ = 'dan'


from base_test import BaseServerTestCase


class BlueprintsTestCase(BaseServerTestCase):

    post_blueprint_args = [
        '/blueprints',
        '/home/dan/dev/cosmo/cosmo-mezzanine-example/mezzanine-app.tar.gz',
        'application_archive',
        'mezzanine-app.tar.gz',
        {'application_file': 'mezzanine-app/mezzanine_blueprint.yaml'}
    ]

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_post_and_then_get(self):
        post_result = self.post_file(*self.post_blueprint_args)
        post_blueprints_response = post_result.json
        self.assertEquals('mezzanine', post_blueprints_response['name'])
        get_result = self.get('/blueprints')
        get_blueprints_response = get_result.json
        self.assertEquals(1, len(get_blueprints_response))
        self.assertEquals(post_blueprints_response, get_blueprints_response[0])

    def test_get_blueprint_by_id(self):
        post_blueprints_response = self.post_file(*self.post_blueprint_args).json
        get_blueprint_by_id_response = self.get('/blueprints/{0}'.format(post_blueprints_response['id'])).json
        self.assertEquals(post_blueprints_response, get_blueprint_by_id_response)

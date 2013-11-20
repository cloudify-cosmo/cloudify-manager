__author__ = 'dan'


from base_test import BaseServerTestCase


class BlueprintsTestCase(BaseServerTestCase):

    def test_get_empty(self):
        result = self.get('/blueprints')
        self.assertEquals(0, len(result.json))

    def test_post(self):
        result = self.post_file('/blueprints',
                                '/home/dan/dev/cosmo/cosmo-mezzanine-example/mezzanine-app.tar.gz',
                                'application_archive',
                                'mezzanine-app.tar.gz',
                                {'application_file': 'mezzanine-app/mezzanine_blueprint.yaml'})
        print result.json

import unittest

import mock

from cloudify_api.server import CloudifyAPI


class CloudifyManagerServiceTest(unittest.TestCase):
    def test_server_init(self):
        app = CloudifyAPI()
        assert app.settings.cloudify_rest_config_file
        assert app.settings.sqlalchemy_dsn is not None
        assert app.logger

    def test_server_load_config_raises(self):
        with mock.patch('manager_rest.config.Config.load_from_file') as m:
            # TypeError when checking if postgresql_host address is IPv6
            s = CloudifyAPI()
            self.assertRaises(TypeError, s.configure)
            m.assert_called_with('/opt/manager/cloudify-rest.conf')

import logging
import unittest

import mock

from cloudify_api.server import CloudifyAPI


class MockConfig:
    async_dsn = 'postgresql+asyncpg://user:secret@localhost/database'
    postgresql_host = 'localhost'
    api_service_log_path = '/dev/null'
    api_service_log_level = 'WARNING'
    warnings: list = []


class CloudifyManagerServiceTest(unittest.TestCase):
    def test_server_init(self):
        with mock.patch('manager_rest.config.instance', MockConfig()) as c:
            s = CloudifyAPI(load_config=False)
            self.assertEqual(c.async_dsn, s.settings.sqlalchemy_database_dsn)
            self.assertEqual(logging.WARNING, s.logger.level)

    def test_server_load_config_raises(self):
        with mock.patch('manager_rest.config.Config.load_from_file') as m:
            # TypeError when checking if postgresql_host address is IPv6
            self.assertRaises(TypeError, CloudifyAPI, load_config=True)
            m.assert_called_with('/opt/manager/cloudify-rest.conf')

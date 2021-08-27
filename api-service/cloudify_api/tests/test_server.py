import logging
from typing import List

import mock
import testtools

from cloudify_api.server import CloudifyAPI


class MockConfig:
    db_url = 'postgresql://user:secret@localhost/database'
    postgresql_host = 'localhost'
    api_service_log_path = '/dev/null'
    api_service_log_level = 'WARNING'
    warnings: List = []


class CloudifyManagerServiceTest(testtools.TestCase):
    def test_server_init(self):
        with mock.patch('manager_rest.config.instance', MockConfig()):
            s = CloudifyAPI(load_config=False)
            self.assertEqual(
                'postgresql+asyncpg://user:secret@localhost/database',
                s.settings.sqlalchemy_database_dsn)
            self.assertEqual(logging.WARNING, s.logger.level)

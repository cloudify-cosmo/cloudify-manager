import logging
from typing import List

import mock
import testtools

from manager_service.server import CloudifyManagerService


class MockConfig:
    db_url = 'postgresql://user:secret@localhost/database'
    manager_service_log_path = '/dev/null'
    manager_service_log_level = 'WARNING'
    warnings: List = []


class CloudifyManagerServiceTest(testtools.TestCase):
    def test_server_init(self):
        with mock.patch('manager_rest.config.instance', MockConfig()) as c:
            s = CloudifyManagerService(load_config=False)
            self.assertEqual(c.db_url, s.settings.sqlalchemy_database_dsn)
            self.assertEqual(logging.WARNING, s.logger.level)

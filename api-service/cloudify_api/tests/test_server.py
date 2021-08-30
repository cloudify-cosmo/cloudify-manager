import logging
from typing import List

import mock
import pytest
import unittest

from cloudify_api.server import CloudifyAPI


class MockConfig:
    async_dsn = 'postgresql+asyncpg://user:secret@localhost/database'
    postgresql_host = 'localhost'
    api_service_log_path = '/dev/null'
    api_service_log_level = 'WARNING'
    warnings: List = []


class CloudifyManagerServiceTest(unittest.TestCase):
    def test_server_init(self):
        with mock.patch('manager_rest.config.instance', MockConfig()) as c:
            s = CloudifyAPI(load_config=False)
            self.assertEqual(c.async_dsn, s.settings.sqlalchemy_database_dsn)
            self.assertEqual(logging.WARNING, s.logger.level)

    def test_server_load_config(self):
        # it's either FileNotFoundError or sqlalchemy.exc.OperationalError
        pytest.raises(Exception, CloudifyAPI, load_config=True)

from testenv import TestCase
from testenv.processes.postgresql import Postgresql


class TestPostgresql(TestCase):

    def setUp(self):
        super(TestPostgresql, self).setUp()

    def _config_db(self):
        self.postgresql = Postgresql()
        self.postgresql.create_db("cloudify_test_db")

    def test_postgres(self):
        self._config_db()

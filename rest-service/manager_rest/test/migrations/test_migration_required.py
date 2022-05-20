import os
import pytest

from manager_rest.test import base_test
from manager_rest import server

from flask_migrate import Migrate, migrate, downgrade


class TestDBMigrations(base_test.BaseServerTestCase):
    def test_no_migrations_required(self):
        Migrate(app=server.app, db=server.db)
        migrate(directory=base_test.MIGRATION_DIR, rev_id='new_test_revision')
        revision_file = os.path.join(
            base_test.MIGRATION_DIR,
            'versions',
            'new_test_revision_.py'
        )
        new_revision_made = os.path.exists(
            revision_file
        )
        if new_revision_made:
            downgrade(directory=base_test.MIGRATION_DIR, revision='-1')
            os.unlink(revision_file)
            pytest.fail('Your code requires a database migration')

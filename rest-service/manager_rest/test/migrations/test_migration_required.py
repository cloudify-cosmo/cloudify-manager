import os
import logging
import pytest

from manager_rest.test import base_test

from flask_migrate import migrate


class TestDBMigrations(base_test.BaseServerTestCase):
    def test_no_migrations_required(self):
        migrate(directory=base_test.MIGRATION_DIR, rev_id='new_test_revision')
        revision_file = os.path.join(
            base_test.MIGRATION_DIR,
            'versions',
            'new_test_revision_.py'
        )
        new_revision_made = os.path.exists(revision_file)
        if new_revision_made:
            with open(revision_file) as f:
                logging.error(
                    "Here's the generated migration:\n %s\n", f.read())
            os.unlink(revision_file)
            pytest.fail('Your code requires a database migration')

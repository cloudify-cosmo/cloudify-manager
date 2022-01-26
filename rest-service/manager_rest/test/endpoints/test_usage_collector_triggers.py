import os

from manager_rest.storage import models
from manager_rest.test import base_test

from flask_migrate import Migrate, downgrade, upgrade

MIGRATION_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', 'resources',
    'rest-service', 'cloudify', 'migrations'
))

class TsetUsageCollectorTriggers(base_test.BaseServerTestCase):

    def test_max_total_deployments(self):
        pass







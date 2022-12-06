import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource as resource

pytestmark = pytest.mark.group_deployments


class BlueprintSetIconTest(AgentlessTestCase):
    def test_blueprint_upload_and_remove_icon(self):
        blueprint_id = 'bp'
        self.client.blueprints.upload(
            resource('dsl/empty_blueprint.yaml'),
            entity_id=blueprint_id
        )
        self.client.blueprints.upload_icon(
            blueprint_id,
            resource('assets/cloudify.png')
        )
        self.client.blueprints.remove_icon(blueprint_id)

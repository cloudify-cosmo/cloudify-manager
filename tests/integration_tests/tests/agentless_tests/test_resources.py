import os
import tempfile
import uuid

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource,
    wait_for_blueprint_upload,
)

pytestmark = pytest.mark.group_deployments


class ResourcesTestCase(AgentlessTestCase):

    def test_download_deployment_workdir(self):
        test_message = "Just a test\n"
        basic_blueprint_path = get_resource('dsl/blueprint_parent.yaml')
        blueprint_id = 'b{0}'.format(uuid.uuid4())
        self.client.blueprints.upload(basic_blueprint_path,
                                      entity_id=blueprint_id)
        wait_for_blueprint_upload(blueprint_id, self.client, True)
        deployment_id = 'd{0}'.format(uuid.uuid4())
        self.client.deployments.create(blueprint_id, deployment_id)

        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(os.path.join(tmp_dir, 'test.txt'), 'wt') as test_file:
                test_file.write(test_message)
            result = self.client.resources.upload_deployment_workdir(
                deployment_id, src_dir=tmp_dir)
            assert result is not None

        with tempfile.TemporaryDirectory() as tmp_dir:
            result = self.client.resources.download_deployment_workdir(
                deployment_id, dst_dir=tmp_dir)
            assert result is not None
            with open(os.path.join(tmp_dir, 'test.txt'), 'rt') as test_file:
                assert test_file.read() == test_message

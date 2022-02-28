import tempfile
import zipfile
from base64 import b64encode

import pytest

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import (
    get_resource as resource,
    wait_for_blueprint_upload,
)


pytestmark = pytest.mark.benchmarks


@pytest.mark.usefixtures('bench')
class BenchmarkRESTSimple(AgentlessTestCase):
    def test_empty_list(self):
        count = 1000
        self.bench.start()
        for _ in range(count):
            bps = self.client.blueprints.list()
            assert len(bps) == 0
        self.bench.stop()


@pytest.mark.usefixtures('bench')
class BenchmarkRESTList(AgentlessTestCase):
    def test_deployments(self):
        # create deployments by using the "restore" API - without running
        # an execution - fastest way to create them. Let's prepare an empty
        # workdir zip.
        count = 1000
        with tempfile.NamedTemporaryFile(mode='rb+') as workdir_zipfile:
            with zipfile.ZipFile(workdir_zipfile, mode='w'):
                pass
            workdir_zipfile.seek(0)
            workdir_zip = b64encode(workdir_zipfile.read()).decode()

        dsl_path = resource("benchmarks/one_node_bp/bp.yaml")
        self.client.blueprints.upload(dsl_path, 'bp1')
        wait_for_blueprint_upload('bp1', self.client)
        self.bench.start('create')
        for i in range(count):
            self.client.deployments.create(
                blueprint_id='bp1',
                deployment_id=f'd{i}',
                _workdir_zip=workdir_zip,
                async_create=False,
            )
        self.bench.stop('create')

        self.bench.start('list')
        for _ in range(100):
            deps = self.client.deployments.list()
            assert len(deps) == count
        self.bench.stop('list')

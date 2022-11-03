import os
import shutil
import tarfile
import tempfile

import mock
import pytest

from cloudify_system_workflows.blueprint import upload


class MockClient:
    def __init__(self, yaml):
        self.blueprints = MockClient.BlueprintClient(yaml)
        self.manager = MockClient.ManagerClient()

    def cleanup(self):
        self.blueprints.cleanup()

    class BlueprintClient:
        def __init__(self, yaml: str):
            self._yaml = yaml
            self._calls = {}
            self._calls.setdefault('update', [])
            self._download_tmp_dirs = []

        def cleanup(self):
            for dir in self._download_tmp_dirs:
                # try:
                shutil.rmtree(dir, ignore_errors=True)
                # except FileNotFoundError:
                #     pass

        def download(self, blueprint_id: str, output_file: str) -> str:
            tmp_dir = tempfile.mkdtemp()
            blueprint_file_name = f'{tmp_dir}{os.sep}{blueprint_id}.yaml'
            with open(blueprint_file_name, 'w+t') as fh:
                fh.write(self._yaml)
            tar_file_name = f'{output_file}{os.sep}{blueprint_id}.tar'
            tar = tarfile.open(tar_file_name, "w")
            tar.add(tmp_dir, arcname=blueprint_id, recursive=True)
            tar.close()
            shutil.rmtree(tmp_dir)
            self._download_tmp_dirs += [output_file]
            return tar_file_name

        def calls(self, function: str):
            return self._calls.get(function, [])

        def update(self, *args, **kwargs):
            self._calls['update'].append({'args': args, 'kwargs': kwargs})

    class ManagerClient:
        def get_context(self):
            return {'context': {}}


def mock_get_client(yaml: str) -> MockClient:
    return MockClient(yaml)


def _test_blueprint_upload(yaml: str, expect=None, **kwargs) -> dict:
    mock_client = mock_get_client(yaml)
    kw = {
        'blueprint_id': 'bp',
        'app_file_name': 'bp.yaml',
        'url': None,
        'file_server_root': f'{os.pathsep}tmp',
        'marketplace_api_url': None,
        'validate_only': True,
        'labels': None,
        'force': False,
    }
    kw.update(kwargs)

    with mock.patch('cloudify_system_workflows.blueprint.get_rest_client',
                    return_value=mock_client):
        if expect:
            with pytest.raises(expect):
                upload(mock.MagicMock(), **kw)
        else:
            upload(mock.MagicMock(), **kw)
    mock_client.cleanup()
    update_calls = mock_client.blueprints.calls('update')
    assert len(update_calls) == 1
    return update_calls[0]


def test_yamllint_warnings():
    yaml = """tosca_definitions_version: cloudify_dsl_1_5

node_types:
  test_type: {  }

node_templates:
  webserver_host:
    type: test_type

  dbserver_host:
    type: test_type

"""
    update_call = _test_blueprint_upload(yaml)
    assert update_call['args'] == ('bp', )
    assert update_call['kwargs']['update_dict']['state'] == 'uploaded'


def test_yamllint_errors_with_force():
    yaml = """tosca_definitions_version: cloudify_dsl_1_5

node_types:
  test_type: {}

node_templates:
  webserver_host:
      type: test_type
  dbserver_host:
    type: test_type
  dbserver_host:
    type: test_type
"""
    update_call = _test_blueprint_upload(yaml, force=True)
    assert update_call['args'] == ('bp', )
    assert update_call['kwargs']['update_dict']['state'] == 'uploaded'

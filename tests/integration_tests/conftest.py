import os
import pytest
import logging
import wagon

import integration_tests_plugins

from collections import namedtuple
from integration_tests.tests import utils as test_utils
from integration_tests.framework import docker
from integration_tests.framework.utils import zip_files
from integration_tests.framework.amqp_events_printer import EventsPrinter
from integration_tests.framework.flask_utils import \
    prepare_reset_storage_script, reset_storage


logger = logging.getLogger('TESTENV')
Env = namedtuple('Env', ['container_id', 'container_ip'])


def pytest_addoption(parser):
    parser.addoption(
        '--image-name',
        help='Name of the Cloudify Manager AIO docker image',
        default='cloudify-manager-aio:latest'
    )
    parser.addoption(
        '--keep-container',
        help='Do not delete the container after tests finish',
        default=False,
        action='store_true'
    )
    parser.addoption(
        '--tests-source-root',
        help='Directory containing cloudify sources to mount',
    )


# items from tests-source-root to be mounted into the specified
# on-manager virtualenvs
# pairs of (source path, [list of target virtualenvs])
# TODO fill this in as needed, when needed
sources = [
    ('cloudify-common/cloudify', ['/opt/manager/env', '/opt/mgmtworker/env']),
    ('cloudify-common/dsl_parser', ['/opt/manager/env']),
    ('cloudify-common/script_runner', ['/opt/mgmtworker/env']),
    ('cloudify-manager/mgmtworker/mgmtworker', ['/opt/mgmtworker/env']),
    ('cloudify-manager/rest-service/manager_rest', ['/opt/manager/env']),
    ('cloudify-manager/rest-service/manager_rest', ['/opt/manager/env']),
    ('cloudify-manager-install/cfy_manager', ['/opt/cloudify/cfy_manager'])
]


def _sources_mounts(request):
    """Mounts for the provided sources.

    The caller can pass --tests-source-root and some directories from
    there will be mounted into the appropriate on-manager venvs.
    """
    sources_root = request.config.getoption("--tests-source-root")
    if not sources_root:
        return
    for src, target_venvs in sources:
        src = os.path.abspath(os.path.join(sources_root, src))
        if os.path.exists(src):
            yield (src, target_venvs)


@pytest.fixture(scope='session')
def resource_mapping(request):
    resources = []
    for src, target_venvs in _sources_mounts(request):
        for venv in target_venvs:
            dst = os.path.join(
                venv, 'lib', 'python3.6', 'site-packages',
                os.path.basename(src))
            resources += [(src, dst)]
    yield resources


@pytest.fixture(scope='class')
def manager_container(request, resource_mapping):
    image_name = request.config.getoption("--image-name")
    keep_container = request.config.getoption("--keep-container")
    container_id = docker.run_manager(
        image_name, resource_mapping=resource_mapping)
    container_ip = docker.get_manager_ip(container_id)
    container = Env(container_id, container_ip)
    request.cls.env = container
    prepare_reset_storage_script(container_id)
    amqp_events_printer_thread = EventsPrinter(
        docker.get_manager_ip(container_id))
    amqp_events_printer_thread.start()
    try:
        yield container
    finally:
        if not keep_container:
            docker.clean(container_id)


@pytest.fixture(autouse=True)
def prepare_manager_storage(request, manager_container):
    """Make sure that for each test, the manager storage is the same.

    This involves uploading the license before the tests, and
    cleaning the db & storage directories between tests.
    """
    container_id = manager_container.container_id
    dirs_to_clean = [
        '/opt/mgmtworker/work/deployments',
        '/opt/manager/resources/blueprints',
        '/opt/manager/resources/uploaded-blueprints'
    ]
    docker.upload_mock_license(container_id)
    try:
        yield
    finally:
        request.session.testsfinished = \
            getattr(request.session, 'testsfinished', 0) + 1
        if request.session.testsfinished != request.session.testscollected:
            reset_storage(container_id)
            for directory in dirs_to_clean:
                docker.execute(
                    container_id,
                    ['sh', '-c', 'rm -rf {0}/*'.format(directory)])


@pytest.fixture(scope='function')
def workdir(request, tmpdir):
    request.cls.workdir = tmpdir


def _make_wagon_fixture(plugin_name):
    """Prepare a session-scoped fixture that creates a plugin wagon."""
    @pytest.fixture(scope='session')
    def _fixture(rest_client, tmp_path_factory):
        plugins_dir = os.path.dirname(integration_tests_plugins.__file__)
        wagon_path = wagon.create(
            os.path.join(plugins_dir, plugin_name),
            archive_destination_dir=str(tmp_path_factory.mktemp(plugin_name)),
            force=True
        )
        yaml_path = os.path.join(plugins_dir, plugin_name, 'plugin.yaml')
        with zip_files([wagon_path, yaml_path]) as zip_path:
            yield zip_path
    _fixture.__name__ = '{0}_wagon'.format(plugin_name)
    return _fixture


def _make_upload_plugin_fixture(plugin_name):
    """Prepare a function-scoped fixture that uploads the plugin.

    That fixture will use the scoped-session wagon fixture and upload it.
    """
    # use exec to be able to dynamically name the parameter. So that
    # this fixture uses the right wagon fixture.
    d = {}
    exec("""
def {0}_plugin(rest_client, {0}_wagon):
    rest_client.plugins.upload({0}_wagon)
""".format(plugin_name), d)
    func = d['{0}_plugin'.format(plugin_name)]
    return pytest.fixture()(func)


cloudmock_wagon = _make_wagon_fixture('cloudmock')
cloudmock_plugin = _make_upload_plugin_fixture('cloudmock')
testmockoperations_wagon = _make_wagon_fixture('testmockoperations')
testmockoperations_plugin = _make_upload_plugin_fixture('testmockoperations')
get_attribute_wagon = _make_wagon_fixture('get_attribute')
get_attribute_plugin = _make_upload_plugin_fixture('get_attribute')
dockercompute_wagon = _make_wagon_fixture('dockercompute')
dockercompute_plugin = _make_upload_plugin_fixture('dockercompute')
target_aware_mock_wagon = _make_wagon_fixture('target_aware_mock')
target_aware_mock_plugin = _make_upload_plugin_fixture('target_aware_mock')

import os
import logging
import pytest
import threading
import wagon

import integration_tests_plugins

from collections import namedtuple
from integration_tests.tests import utils as test_utils
from integration_tests.framework import docker
from integration_tests.framework.utils import zip_files
from integration_tests.framework.amqp_events_printer import print_events
from integration_tests.framework.flask_utils import \
    prepare_reset_storage_script, reset_storage


logger = logging.getLogger('TESTENV')
Env = namedtuple('Env', ['container_id', 'container_ip', 'service_management'])

test_groups = [
    'group_deployments', 'group_service_composition', 'group_scale',
    'group_snapshots', 'group_premium', 'group_agents', 'group_rest',
    'group_plugins', 'group_workflows', 'group_environments', 'group_dsl',
    'group_events_logs', 'group_usage_collector', 'group_general',
    'group_deployments_large_scale'
]


def pytest_collection_modifyitems(items, config):
    for item in items:
        if not [m for m in item.iter_markers() if m.name in test_groups]:
            raise Exception('Test {} not marked as belonging to any known '
                            'test group!'.format(item.nodeid))


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
    parser.addoption(
        '--container-id',
        help='Run integration tests on this container',
    )
    parser.addoption(
        '--service-management',
        default='supervisord',
        help='Run integration tests using specific service management layer. '
             '`supervisord` or `systemd`',
    )


# items from tests-source-root to be mounted into the specified
# on-manager virtualenvs
# pairs of (source path, [list of target virtualenvs])
# TODO fill this in as needed, when needed
sources = [
    ('cloudify-cli/cloudify_cli', ['/opt/cfy']),
    ('cloudify-premium/cloudify_premium', ['/opt/manager/env']),
    ('cloudify-common/cloudify', ['/opt/manager/env', '/opt/mgmtworker/env',
                                  '/opt/cfy']),
    ('cloudify-common/cloudify_rest_client', [
        '/opt/manager/env', '/opt/mgmtworker/env', '/opt/cfy']),
    ('cloudify-common/cloudify_rest_client', ['/opt/mgmtworker/env']),
    ('cloudify-common/dsl_parser', ['/opt/manager/env',
                                    '/opt/mgmtworker/env']),
    ('cloudify-common/script_runner', ['/opt/mgmtworker/env']),
    ('cloudify-agent/cloudify_agent', ['/opt/mgmtworker/env']),
    ('cloudify-manager/mgmtworker/mgmtworker', ['/opt/mgmtworker/env']),
    ('cloudify-manager/rest-service/manager_rest', ['/opt/manager/env']),
    ('cloudify-manager/workflows/cloudify_system_workflows', ['/opt/mgmtworker/env']),  # NOQA
    ('cloudify-manager/cloudify_types/cloudify_types', ['/opt/mgmtworker/env']),  # NOQA
    ('cloudify-manager-install/cfy_manager', ['/opt/cloudify/cfy_manager']),
    ('cloudify-manager/execution-scheduler/execution_scheduler', ['/opt/manager/env']),  # NOQA
]

# like sources, but just static files, not in a venv. Provide target
# directory directly.
sources_static = [
    (
        'cloudify-manager/resources/rest-service/cloudify/migrations',
        ['/opt/manager/resources/cloudify/migrations']),
]


@pytest.fixture(scope='session')
def resource_mapping(request):
    """Mounts for the provided sources.

    The caller can pass --tests-source-root and some directories from
    there will be mounted into the appropriate on-manager venvs.
    """
    sources_root = request.config.getoption("--tests-source-root")
    resources = []
    if sources_root:
        for src, target_venvs in sources:
            src = os.path.abspath(os.path.join(sources_root, src))
            if not os.path.exists(src):
                continue
            for venv in target_venvs:
                dst = os.path.join(
                    venv, 'lib', 'python3.6', 'site-packages',
                    os.path.basename(src))
                resources += [(src, dst)]

        for src, targets in sources_static:
            src = os.path.abspath(os.path.join(sources_root, src))
            if not os.path.exists(src):
                continue
            for dst in targets:
                resources += [(src, dst)]

    yield resources


@pytest.fixture(scope='session')
def manager_container(request, resource_mapping):
    image_name = request.config.getoption("--image-name")
    keep_container = request.config.getoption("--keep-container")
    container_id = request.config.getoption("--container-id")
    service_management = request.config.getoption("--service-management")
    if container_id:
        reset_storage(container_id)
        keep_container = True
    else:
        container_id = docker.run_manager(
            image_name, service_management, resource_mapping=resource_mapping)
        docker.upload_mock_license(container_id)
    container_ip = docker.get_manager_ip(container_id)
    container = Env(container_id, container_ip, service_management)
    prepare_reset_storage_script(container_id)
    amqp_events_printer_thread = threading.Thread(
        target=print_events, args=(container_id, ))
    amqp_events_printer_thread.daemon = True
    amqp_events_printer_thread.start()
    _disable_cron_jobs(container_id)
    try:
        yield container
    finally:
        if not keep_container:
            docker.clean(container_id)


@pytest.fixture(scope='session')
def ca_cert(manager_container, tmpdir_factory):
    cert_path = tmpdir_factory.mktemp('certs').join('internal_ca_cert.pem')
    docker.copy_file_from_manager(
        manager_container.container_id,
        '/etc/cloudify/ssl/cloudify_internal_ca_cert.pem',
        cert_path)
    yield cert_path


@pytest.fixture(scope='session')
def rest_client(manager_container, ca_cert):
    client = test_utils.create_rest_client(
        host=manager_container.container_ip,
        rest_port=443,
        rest_protocol='https',
        cert_path=ca_cert
    )
    yield client


@pytest.fixture(scope='class')
def manager_class_fixtures(request, manager_container, rest_client, ca_cert):
    """Just a hack to put some fixtures on the test class.

    This is for compatibility with class-based tests, who don't have
    a better way of using fixtures. Eventually, those old tests will
    transition to be function-based, and they won't need to use this.
    """
    request.cls.env = manager_container
    request.cls.client = rest_client
    request.cls.ca_cert = ca_cert


@pytest.fixture(autouse=True)
def prepare_manager_storage(request, manager_container):
    """Make sure that for each test, the manager storage is the same.

    This involves uploading the license before the tests, and
    cleaning the db & storage directories between tests.
    """
    container_id = manager_container.container_id
    try:
        yield
    finally:
        request.session.testsfinished = \
            getattr(request.session, 'testsfinished', 0) + 1
        if request.session.testsfinished != request.session.testscollected:
            reset_storage(container_id)


@pytest.fixture(scope='session')
def allow_agent(manager_container, package_agent):
    """Allow installing an agent on the manager container.

    Agent installation scripts have all kinds of assumptions about
    sudo and su, so those need to be available.
    """
    docker.execute(manager_container.container_id, [
        'bash', '-c',
        "echo 'cfyuser ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/cfyuser"
    ])
    docker.execute(manager_container.container_id, [
        'sed', '-i',
        "1iauth sufficient pam_succeed_if.so user = cfyuser",
        '/etc/pam.d/su'
    ])


@pytest.fixture(scope='session')
def package_agent(manager_container, request):
    """Repackage the on-manager agent with the provided sources.

    If the user provides sources (--tests-source-root), then
    not only are those mounted into the mgmtworker and manager,
    but they will also be put into the agent package that is used in
    the tests.

    All the sources that are mounted to the mgmtworker env, will
    also be used for the agent.
    """
    sources_root = request.config.getoption("--tests-source-root")
    if not sources_root:
        return
    # unpack the agent archive, overwrite files, repack it, copy back
    # to the package location
    mgmtworker_env = '/opt/mgmtworker/env/lib/python*/site-packages/'
    agent_package = \
        '/opt/manager/resources/packages/agents/centos-core-agent.tar.gz'
    agent_source_path = 'cloudify/env/lib/python*/site-packages/'
    agent_sources = []
    for src, target_venvs in sources:
        src = os.path.abspath(os.path.join(sources_root, src))
        if not os.path.exists(src):
            continue
        if '/opt/mgmtworker/env' in target_venvs:
            agent_sources.append(os.path.basename(src))
    if not agent_sources:
        return
    docker.execute(manager_container.container_id, [
        'bash', '-c', 'cd /tmp && tar xvf {0}'.format(agent_package)
    ])
    for package in agent_sources:
        source = os.path.join(mgmtworker_env, package)
        target = os.path.join('/tmp', agent_source_path)
        docker.execute(manager_container.container_id, [
            'bash', '-c',
            'cp -fr {0} {1}'.format(source, target)
        ])
    docker.execute(manager_container.container_id, [
        'bash', '-c',
        'cd /tmp && tar czf centos-core-agent.tar.gz cloudify'
    ])
    docker.execute(manager_container.container_id, [
        'mv', '-f',
        '/tmp/centos-core-agent.tar.gz',
        agent_package
    ])


@pytest.fixture(scope='function')
def workdir(request, tmpdir):
    request.cls.workdir = tmpdir


def _make_wagon_fixture(plugin_name):
    """Prepare a session-scoped fixture that creates a plugin wagon."""
    @pytest.fixture(scope='session')
    def _fixture(rest_client, tmp_path_factory):
        plugins_dir = os.path.dirname(integration_tests_plugins.__file__)
        plugin_source = os.path.join(plugins_dir, plugin_name)
        wagon_path = wagon.create(
            plugin_source,
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
    rest_client.plugins.upload({0}_wagon, visibility='global')
""".format(plugin_name), d)
    func = d['{0}_plugin'.format(plugin_name)]
    return pytest.fixture()(func)


def _disable_cron_jobs(container_id):
    if docker.file_exists(container_id, '/var/spool/cron/cfyuser'):
        docker.execute(container_id, 'crontab -u cfyuser -r')


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
mock_workflows_wagon = _make_wagon_fixture('mock_workflows')
mock_workflows_plugin = _make_upload_plugin_fixture('mock_workflows')
version_aware_wagon = _make_wagon_fixture('version_aware')
version_aware_plugin = _make_upload_plugin_fixture('version_aware')
version_aware_v2_wagon = _make_wagon_fixture('version_aware_v2')
version_aware_v2_plugin = _make_upload_plugin_fixture('version_aware_v2')

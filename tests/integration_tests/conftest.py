import logging
import os
import subprocess

import pytest
import wagon

import integration_tests_plugins
from integration_tests.framework.flask_utils import \
    prepare_reset_storage_script, reset_storage
from integration_tests.framework import utils
from integration_tests.tests import utils as test_utils

logger = logging.getLogger('TESTENV')


test_groups = [
    'group_deployments', 'group_service_composition', 'group_scale',
    'group_snapshots', 'group_premium', 'group_agents', 'group_rest',
    'group_plugins', 'group_workflows', 'group_environments', 'group_dsl',
    'group_events_logs', 'group_usage_collector', 'group_general',
    'group_deployments_large_scale', 'group_api', 'benchmarks',
]


def pytest_collection_modifyitems(items, config):
    for item in items:
        if not [m for m in item.iter_markers() if m.name in test_groups]:
            raise Exception(f'Test {item.nodeid} not marked as belonging '
                            'to any known test group!')


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
        '--k8s-namespace',
        help='Run integration tests in this Kubernetes namespace',
    )
    parser.addoption(
        '--lightweight',
        default=False,
        action='store_true',
        help='Run a "lightweight" manager, without UI and monitoring',
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
    ('cloudify-common/cloudify_async_client', [
        '/opt/manager/env', '/opt/mgmtworker/env', '/opt/cfy']),
    ('cloudify-common/dsl_parser', ['/opt/manager/env',
                                    '/opt/mgmtworker/env']),
    ('cloudify-common/script_runner', ['/opt/mgmtworker/env']),
    ('cloudify-agent/cloudify_agent', ['/opt/mgmtworker/env']),
    ('cloudify-manager/mgmtworker/mgmtworker', ['/opt/mgmtworker/env']),
    ('cloudify-manager/rest-service/manager_rest', ['/opt/manager/env']),
    ('cloudify-manager/api-service/cloudify_api', ['/opt/manager/env']),
    ('cloudify-manager/amqp-postgres/amqp_postgres', ['/opt/manager/env']),
    ('cloudify-manager/mgmtworker/cloudify_system_workflows', ['/opt/mgmtworker/env']),  # NOQA
    ('cloudify-manager/mgmtworker/cloudify_types', ['/opt/mgmtworker/env']),
    ('cloudify-manager-install/cfy_manager', ['/opt/cloudify/cfy_manager']),
    ('cloudify-manager-install/config.yaml', ['/opt/cloudify/cfy_manager']),
    ('cloudify-manager/execution-scheduler/execution_scheduler', ['/opt/manager/env']),  # NOQA
]

# like sources, but just static files, not in a venv. Provide target
# directory directly.
sources_static = [
    (
        'cloudify-manager/rest-service/migrations',
        ['/opt/manager/resources/cloudify/migrations']
    ),
    (
        'cloudify-manager/resources/rest-service/cloudify/types/types.yaml',
        ['/opt/manager/resources/cloudify/types/types.yaml']
    ),
    (
        'cloudify-manager/resources/rest-service/cloudify/types/'
        'types_1_3.yaml',
        ['/opt/manager/resources/cloudify/types/types_1_3.yaml']
    ),
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
                    venv, 'lib', 'python3.11', 'site-packages',
                    os.path.basename(src))
                resources += [(src, dst)]

        for src, targets in sources_static:
            src = os.path.abspath(os.path.join(sources_root, src))
            if not os.path.exists(src):
                continue
            for dst in targets:
                resources += [(src, dst)]

    yield resources


def prepare_events_follower(environment):
    environment.copy_file_to_manager(
        test_utils.get_resource('scripts/follow_events.py'),
        '/tmp/follow_events.py'
    )


@pytest.fixture(autouse=True)
def start_events_follower(tests_env):
    follower = tests_env.run_python_on_manager(['-u', '/tmp/follow_events.py'])
    yield
    follower.kill()
    try:
        tests_env.execute_on_manager(['pkill', '-f', 'follow_events.py'])
    except subprocess.CalledProcessError:
        pass


@pytest.fixture(scope='session')
def tests_env(request, resource_mapping) -> utils.TestEnvironment:
    image_name = request.config.getoption("--image-name")
    keep_container = request.config.getoption("--keep-container")
    container_id = request.config.getoption("--container-id")
    k8s_ns = request.config.getoption("--k8s-namespace")
    lightweight = request.config.getoption('--lightweight')
    if container_id and k8s_ns:
        raise Exception('Expecting either `--container-id` or '
                        '`--k8s_namespace`, not both.')

    if container_id:
        keep_container = True
        environment = utils.AllInOneEnvironment(container_id)
        prepare_reset_storage_script(environment)
        reset_storage(environment)
    elif k8s_ns:
        environment = utils.DistributedEnvironment(k8s_ns)
        prepare_reset_storage_script(environment)
        reset_storage(environment)
    else:
        environment = utils.start_manager_container(
            image_name,
            resource_mapping=resource_mapping,
            lightweight=lightweight,
        )
        prepare_reset_storage_script(environment)
        utils.upload_mock_license(environment)
    prepare_events_follower(environment)
    _disable_cron_jobs(environment)
    yield environment
    if not keep_container:
        environment.cleanup()


@pytest.fixture(scope='session')
def ca_cert(tests_env, tmpdir_factory):
    cert_path = tmpdir_factory.mktemp('certs').join('internal_ca_cert.pem')
    ca_cert = tests_env.ca_cert()
    with open(cert_path, 'wt') as cert_file:
        cert_file.write(ca_cert)
    yield cert_path


@pytest.fixture(scope='session')
def rest_client(tests_env, ca_cert):
    yield tests_env.rest_client(ca_cert)


@pytest.fixture(scope='class')
def manager_class_fixtures(request, tests_env, rest_client, ca_cert):
    """Just a hack to put some fixtures on the test class.

    This is for compatibility with class-based tests, who don't have
    a better way of using fixtures. Eventually, those old tests will
    transition to be function-based, and they won't need to use this.
    """
    request.cls.env = tests_env
    request.cls.client = rest_client
    request.cls.ca_cert = ca_cert


@pytest.fixture(autouse=True)
def prepare_manager_storage(request, tests_env):
    """Make sure that for each test, the manager storage is the same.

    This involves uploading the license before the tests, and
    cleaning the db & storage directories between tests.
    """
    try:
        yield
    finally:
        request.session.testsfinished = \
            getattr(request.session, 'testsfinished', 0) + 1
        if request.session.testsfinished != request.session.testscollected:
            reset_storage(tests_env)


@pytest.fixture(scope='session')
def allow_agent(tests_env, package_agent):
    """Allow installing an agent on the manager container.

    Agent installation scripts have all kinds of assumptions about
    sudo and su, so those need to be available.
    """
    tests_env.execute_on_manager([
        'bash',
        '-c',
        "echo 'cfyuser ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/cfyuser",
    ])
    tests_env.execute_on_manager([
        'sed',
        '-i',
        "1iauth sufficient pam_succeed_if.so user = cfyuser",
        '/etc/pam.d/su'
    ])


@pytest.fixture(scope='session')
def package_agent(tests_env, request):
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
        '/opt/manager/resources/packages/agents/manylinux-x86_64-agent.tar.gz'
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
    tests_env.execute_on_manager([
        'bash', '-c', f'cd /tmp && tar xvf {agent_package}'
    ])
    for package in agent_sources:
        source = os.path.join(mgmtworker_env, package)
        target = os.path.join('/tmp', agent_source_path)
        tests_env.execute_on_manager([
            'bash', '-c', f'cp -fr {source} {target}'
        ])
    tests_env.execute_on_manager([
        'bash', '-c',
        'cd /tmp && tar czf manylinux-x86_64-agent.tar.gz cloudify'
    ])
    tests_env.execute_on_manager([
        'mv', '-f', '/tmp/manylinux-x86_64-agent.tar.gz', agent_package
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
        with utils.zip_files([wagon_path, yaml_path]) as zip_path:
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


def _disable_cron_jobs(environment):
    if environment.file_exists_on_manager('/var/spool/cron/cfyuser'):
        environment.execute_on_manager(['crontab', '-u', 'cfyuser', '-r'])


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
mock_labels_wagon = _make_wagon_fixture('mock_labels')
mock_labels_plugin = _make_upload_plugin_fixture('mock_labels')
dsl_backcompat_wagon = _make_wagon_fixture('dsl_backcompat')
dsl_backcompat_plugin = _make_upload_plugin_fixture('dsl_backcompat')
with_properties_wagon = _make_wagon_fixture('with_properties')
with_properties_plugin = _make_upload_plugin_fixture('with_properties')

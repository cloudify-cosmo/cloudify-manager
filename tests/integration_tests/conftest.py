import os
import pytest
import logging
from itertools import chain

import integration_tests_plugins
import fasteners

from collections import namedtuple
from integration_tests.framework import docker
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


def _plugin_mounts():
    """Mounts for local plugins.

    Plugins defined inside the integration-tests directories are
    mounted to the container mgmtworker env, to be used in test
    workflows.
    """
    venvs = ['/opt/mgmtworker/env', '/opt/agent-template/env']
    plugins_dir = os.path.dirname(integration_tests_plugins.__file__)
    fasteners_dir = os.path.dirname(fasteners.__file__)

    for directory in os.listdir(plugins_dir):
        directory = os.path.join(plugins_dir, directory)
        if not os.path.isdir(directory):
            continue
        yield (directory, venvs)

    yield (fasteners_dir, venvs)
    yield (plugins_dir, venvs)


@pytest.fixture(scope='session')
def resource_mapping(request):
    resources = []
    for src, target_venvs in chain(_sources_mounts(request), _plugin_mounts()):
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
def clean_manager_storage(request, manager_container):
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
    yield

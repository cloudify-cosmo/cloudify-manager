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

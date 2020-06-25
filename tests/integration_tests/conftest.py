import pytest
from integration_tests.framework import env


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
def test_environment(request):
    image_name = request.config.getoption("--image-name")
    keep_container = request.config.getoption("--keep-container")
    request.cls.env = env.create_env(request.cls.environment_type, image_name)
    try:
        yield
    finally:
        if not keep_container:
            env.destroy_env()

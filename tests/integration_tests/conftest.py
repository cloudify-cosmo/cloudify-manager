import pytest
from integration_tests.framework import env


def pytest_addoption(parser):
    parser.addoption(
        '--image-name',
        help='Name of the Cloudify Manager AIO docker image',
        default='cloudify-manager-aio'
    )


@pytest.fixture(scope='class')
def test_environment(request):
    image_name = request.config.getoption("--image-name")
    request.cls.env = env.create_env(request.cls.environment_type, image_name)
    try:
        yield
    finally:
        env.destroy_env()

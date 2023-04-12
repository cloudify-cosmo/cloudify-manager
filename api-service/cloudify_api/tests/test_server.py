import mock
import pytest

from cloudify_api.server import CloudifyAPI


def test_server_init():
    app = CloudifyAPI()
    assert app.logger


def test_server_load_config_raises():
    with mock.patch('manager_rest.config.Config.load_from_file') as m:
        # TypeError when checking if postgresql_host address is IPv6
        s = CloudifyAPI()
        with pytest.raises(TypeError):
            s.configure()
    m.assert_has_calls([
        mock.call('/opt/manager/cloudify-rest.conf', ''),
        mock.call('/opt/manager/rest-security.conf', 'security'),
    ])

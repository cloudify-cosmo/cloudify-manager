from .. import acfy
from manager_rest.rest.resources_v3_1.manager import (
    SSLConfig,
    DEFAULT_CONF_PATH,
    HTTP_PATH,
    HTTPS_PATH)


@acfy.group(name='ssl')
def ssl():
    pass


@ssl.command(name='status')
@acfy.pass_logger
def ssl_status(logger):
    logger.info('SSL {0}'.format(
                'enabled' if SSLConfig._is_enabled() else 'disabled'))


def _set_nginx_ssl(enabled):
    with open(DEFAULT_CONF_PATH) as f:
        config = f.read()
    if enabled:
        config = config.replace(HTTP_PATH, HTTPS_PATH)
    else:
        config = config.replace(HTTPS_PATH, HTTP_PATH)
    with open(DEFAULT_CONF_PATH, 'w') as f:
        f.write(config)


@ssl.command(name='enable')
def ssl_enable():
    _set_nginx_ssl(True)


@ssl.command(name='disable')
def ssl_disable():
    _set_nginx_ssl(False)

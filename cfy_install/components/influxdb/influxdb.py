from os.path import join

from ..service_names import INFLUXB, MANAGER

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.network import wait_for_port
from ...utils.systemd import systemd


# currently, cannot be changed due to webui not allowing to configure it.
INFLUXDB_ENDPOINT_PORT = 8086
logger = get_logger(INFLUXB)


def _install():
    influxdb_endpoint_ip = config[INFLUXB]['influxdb_endpoint_ip']

    if influxdb_endpoint_ip:
        logger.info('External InfluxDB Endpoint IP provided: {0}'.format(
            influxdb_endpoint_ip))
        wait_for_port(INFLUXDB_ENDPOINT_PORT, influxdb_endpoint_ip)
        _configure_influxdb(influxdb_endpoint_ip, INFLUXDB_ENDPOINT_PORT)
    else:
        influxdb_endpoint_ip = config[MANAGER]['private_ip']
        config[INFLUXB]['influxdb_endpoint_ip'] = influxdb_endpoint_ip

        _install()
        systemd.restart(INFLUXB)

        wait_for_port(INFLUXDB_ENDPOINT_PORT, influxdb_endpoint_ip)
        _configure_influxdb(influxdb_endpoint_ip, INFLUXDB_ENDPOINT_PORT)

        systemd.stop(INFLUXB)


def install():
    logger.notice('Installing InfluxDB...')
    _install()
    logger.notice('InfluxDB installed successfully')


def configure():
    pass

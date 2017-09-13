import json
from os.path import join

from ..service_names import INFLUXB, MANAGER

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils.systemd import systemd
from ...utils.deploy import copy_notice
from ...utils.install import yum_install
from ...utils.logrotate import set_logrotate
from ...utils.network import wait_for_port, check_http_response

logger = get_logger(INFLUXB)

# Currently, cannot be changed due to webui not allowing to configure it.
INFLUXDB_ENDPOINT_PORT = 8086

HOME_DIR = join('/opt', INFLUXB)
LOG_DIR = join(constants.BASE_LOG_DIR, INFLUXB)
INIT_D_PATH = join('/etc', 'init.d', INFLUXB)
CONFIG_PATH = join(constants.COMPONENTS_DIR, INFLUXB, 'config')


def _configure_influxdb(host, port):
    db_user = "root"
    db_pass = "root"
    db_name = "cloudify"

    logger.info('Creating InfluxDB Database...')

    # the below request is equivalent to running:
    # curl -S -s "http://localhost:8086/db?u=root&p=root" '-d "{\"name\": \"cloudify\"}"  # NOQA
    import urllib
    import urllib2
    import ast

    endpoint_for_list = 'http://{0}:{1}/db'.format(host, port)
    endpoint_for_creation = ('http://{0}:{1}/cluster/database_configs/'
                             '{2}'.format(host, port, db_name))
    params = urllib.urlencode(dict(u=db_user, p=db_pass))
    url_for_list = endpoint_for_list + '?' + params
    url_for_creation = endpoint_for_creation + '?' + params

    # check if db already exists
    db_list = eval(urllib2.urlopen(urllib2.Request(url_for_list)).read())
    try:
        assert not any(d.get('name') == db_name for d in db_list)
    except AssertionError:
        logger.info('Database {0} already exists!'.format(db_name))
        return

    try:
        tmp_path = common.temp_copy(join(CONFIG_PATH, 'retention.json'))

        with open(tmp_path) as policy_file:
            retention_policy = policy_file.read()
        logger.debug(
            'Using retention policy: \n{0}'.format(retention_policy))
        data = json.dumps(ast.literal_eval(retention_policy))
        logger.debug('Using retention policy: \n{0}'.format(data))
        content_length = len(data)
        request = urllib2.Request(url_for_creation, data, {
            'Content-Type': 'application/json',
            'Content-Length': content_length})
        logger.debug('Request is: {0}'.format(request))
        request_reader = urllib2.urlopen(request)
        response = request_reader.read()
        logger.debug('Response: {0}'.format(response))
        request_reader.close()
        common.remove('/tmp/retention.json')

    except Exception as ex:
        raise StandardError('Failed to create: {0} ({1}).'.format(db_name, ex))

    # verify db created
    logger.info('Verifying database create successfully...')
    db_list = eval(urllib2.urlopen(urllib2.Request(url_for_list)).read())
    try:
        assert any(d.get('name') == db_name for d in db_list)
    except AssertionError:
        raise StandardError('Verification failed!')
    logger.info('Databased {0} created successfully.'.format(db_name))


def _install_influxdb():
    source_url = config[INFLUXB]['sources']['influxdb_source_url']
    yum_install(source_url)


def _install():
    influxdb_endpoint_ip = config[INFLUXB]['endpoint_ip']

    if influxdb_endpoint_ip:
        config[INFLUXB]['external'] = True
        logger.info('External InfluxDB Endpoint IP provided: {0}'.format(
            influxdb_endpoint_ip))
    else:
        config[INFLUXB]['external'] = False
        influxdb_endpoint_ip = config[MANAGER]['private_ip']
        config[INFLUXB]['endpoint_ip'] = influxdb_endpoint_ip

        _install_influxdb()
        systemd.restart(INFLUXB)


def _create_paths():
    common.mkdir(HOME_DIR)
    common.mkdir(LOG_DIR)

    _deploy_config_file()

    common.chown(INFLUXB, INFLUXB, HOME_DIR)
    common.chown(INFLUXB, INFLUXB, LOG_DIR)


def _deploy_config_file():
    logger.info('Deploying InfluxDB configuration...')
    common.copy(
        source=join(CONFIG_PATH, 'config.toml'),
        destination=join(HOME_DIR, 'shared', 'config.toml')
    )


def _configure_local_influxdb():
    config[INFLUXB]['service_user'] = INFLUXB
    config[INFLUXB]['service_group'] = INFLUXB

    _create_paths()
    copy_notice(INFLUXB)

    systemd.configure(INFLUXB)
    # Provided with InfluxDB's package. Will be removed if it exists.
    common.remove(INIT_D_PATH)
    set_logrotate(INFLUXB)


def _check_response():
    influxdb_endpoint_ip = config[INFLUXB]['endpoint_ip']
    influxdb_url = 'http://{0}:{1}'.format(
        influxdb_endpoint_ip,
        INFLUXDB_ENDPOINT_PORT
    )
    response = check_http_response(influxdb_url)

    # InfluxDB normally responds with a 404 on GET to /, but also allow other
    # non-server-error response codes to allow for that behaviour to change.
    if response.code >= 500:
        raise StandardError('Could not validate InfluxDB')


def _start_and_verify_alive():
    logger.info('Starting InfluxDB Service...')
    systemd.restart(INFLUXB)
    systemd.verify_alive(INFLUXB)
    wait_for_port(INFLUXDB_ENDPOINT_PORT)
    _check_response()


def _configure():
    influxdb_endpoint_ip = config[INFLUXB]['endpoint_ip']
    wait_for_port(INFLUXDB_ENDPOINT_PORT, influxdb_endpoint_ip)
    _configure_influxdb(influxdb_endpoint_ip, INFLUXDB_ENDPOINT_PORT)
    if not config[INFLUXB]['external']:
        _configure_local_influxdb()
        _start_and_verify_alive()


def install():
    logger.notice('Installing InfluxDB...')
    _install()
    _configure()
    logger.notice('InfluxDB installed successfully')


def configure():
    logger.notice('Configuring InfluxDB...')
    _configure()
    logger.notice('InfluxDB successfully configured')

from os.path import join
from collections import namedtuple

from .. import SOURCES, CONFIG, PRIVATE_IP, PUBLIC_IP

from ..service_names import NGINX, AGENT, MANAGER, SSL_INPUTS

from ... import constants
from ...config import config
from ...logger import get_logger
from ...exceptions import ValidationError

from ...utils import common
from ...utils import certificates
from ...utils.systemd import systemd
from ...utils.install import yum_install, yum_remove
from ...utils.logrotate import set_logrotate, remove_logrotate
from ...utils.files import remove_files, deploy, copy_notice, remove_notice

LOG_DIR = join(constants.BASE_LOG_DIR, NGINX)
CONFIG_PATH = join(constants.COMPONENTS_DIR, NGINX, CONFIG)
UNIT_OVERRIDE_PATH = '/etc/systemd/system/nginx.service.d'

logger = get_logger(NGINX)


def _install():
    nginx_source_url = config[NGINX][SOURCES]['nginx_source_url']
    yum_install(nginx_source_url)


def _deploy_unit_override():
    logger.debug('Creating systemd unit override...')
    unit_override_path = '/etc/systemd/system/nginx.service.d'
    common.mkdir(unit_override_path)
    deploy(
        src=join(CONFIG_PATH, 'restart.conf'),
        dst=join(unit_override_path, 'restart.conf')
    )


def _generate_internal_certs(internal_rest_host):
    logger.info('Creating internal certificate...')
    networks = config[AGENT]['networks']

    certificates.store_cert_metadata(internal_rest_host, networks)
    cert_ips = [internal_rest_host] + list(networks.values())
    certificates.generate_internal_ssl_cert(
        ips=cert_ips,
        name=internal_rest_host
    )


def _generate_external_certs(internal_rest_host):
    logger.info('Creating external certificate...')
    external_rest_host = config[MANAGER][PUBLIC_IP]

    certificates.deploy_or_generate_external_ssl_cert(
        ips=[external_rest_host, internal_rest_host],
        cn=external_rest_host,
        cert_path=config[SSL_INPUTS]['external_cert_path'],
        key_path=config[SSL_INPUTS]['external_key_path']
    )


def _create_certs():
    # Needs to be run here, because openssl is required and is
    # installed by nginx
    common.remove(constants.SSL_CERTS_TARGET_DIR)
    common.mkdir(constants.SSL_CERTS_TARGET_DIR)

    logger.info('Creating CA certificate...')
    certificates.generate_ca_cert()

    internal_rest_host = config[MANAGER][PRIVATE_IP]
    _generate_internal_certs(internal_rest_host)
    _generate_external_certs(internal_rest_host)


def _deploy_nginx_config_files():
    logger.info('Deploying Nginx configuration files...')
    resource = namedtuple('Resource', 'src dst')

    resources = [
        resource(
            src='{0}/http-external-rest-server.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/http-external-rest-server.cloudify'
        ),
        resource(
            src='{0}/https-external-rest-server.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/https-external-rest-server.cloudify'
        ),
        resource(
            src='{0}/https-internal-rest-server.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/https-internal-rest-server.cloudify'
        ),
        resource(
            src='{0}/https-file-server.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/https-file-server.cloudify'
        ),
        resource(
            src='{0}/nginx.conf'.format(CONFIG_PATH),
            dst='/etc/nginx/nginx.conf'
        ),
        resource(
            src='{0}/default.conf'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/default.conf',
        ),
        resource(
            src='{0}/rest-location.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/rest-location.cloudify',
        ),
        resource(
            src='{0}/fileserver-location.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/fileserver-location.cloudify',
        ),
        resource(
            src='{0}/redirect-to-fileserver.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/redirect-to-fileserver.cloudify',
        ),
        resource(
            src='{0}/ui-locations.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/ui-locations.cloudify',
        ),
        resource(
            src='{0}/composer-location.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/composer-location.cloudify',
        ),
        resource(
            src='{0}/logs-conf.cloudify'.format(CONFIG_PATH),
            dst='/etc/nginx/conf.d/logs-conf.cloudify',
        )
    ]

    for resource in resources:
        deploy(resource.src, resource.dst)


def _verify_nginx():
    # TODO: This code requires the restservice to be installed, but
    # restservice depends on rabbitmq, which in turn requires the certificates
    # created in nginx (here). So we need to find an other way to validate it
    logger.info('Verifying NGINX service is up...')
    nginx_url = 'https://127.0.0.1:{0}/api/v2.1/version'.format(
        config[NGINX]['internal_rest_port']
    )
    output = common.run([
        'curl',
        nginx_url,
        '--cacert', constants.CA_CERT_PATH,
        # only output the http code
        '-o', '/dev/null',
        '-w', '%{http_code}'
    ])
    if output.aggr_stdout.strip() not in {'200', '401'}:
        raise ValidationError('Nginx HTTP check error: {0}'.format(output))


def _start_and_verify_service():
    logger.info('Starting NGINX service...')
    systemd.enable(NGINX, append_prefix=False)
    systemd.restart(NGINX, append_prefix=False)
    systemd.verify_alive(NGINX, append_prefix=False)
    # _verify_nginx()


def _configure():
    common.mkdir(LOG_DIR)
    copy_notice(NGINX)
    _deploy_unit_override()
    set_logrotate(NGINX)
    _create_certs()
    _deploy_nginx_config_files()
    _start_and_verify_service()


def install():
    logger.notice('Installing NGINX...')
    _install()
    _configure()
    logger.notice('NGINX successfully installed')


def configure():
    logger.notice('Configuring NGINX...')
    _configure()
    logger.notice('NGINX successfully configured')


def remove():
    logger.notice('Removing NGINX...')
    remove_notice(NGINX)
    remove_logrotate(NGINX)
    remove_files([
        join('/etc', NGINX),
        join('/var/log', NGINX),
        join('/var/cache', NGINX),
        LOG_DIR,
        UNIT_OVERRIDE_PATH
    ])
    yum_remove(NGINX)
    logger.notice('NGINX successfully removed')

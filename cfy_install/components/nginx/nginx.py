from os.path import join
from collections import namedtuple

from ..service_names import NGINX, AGENT

from ... import constants
from ...config import config
from ...logger import get_logger

from ...utils import common
from ...utils import certificates
from ...utils.systemd import systemd
from ...utils.install import yum_install
from ...utils.logrotate import set_logrotate
from ...utils.deploy import copy_notice, deploy

LOG_DIR = join(constants.BASE_LOG_DIR, NGINX)
CONFIG_PATH = join(constants.COMPONENTS_DIR, NGINX, 'config')

logger = get_logger(NGINX)


def _install():
    nginx_source_url = config[NGINX]['sources']['nginx_source_url']
    yum_install(nginx_source_url)


def _deploy_unit_override():
    logger.info('Creating systemd unit override...')
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
    external_rest_host = config[NGINX]['external_rest_host']

    certificates.deploy_or_generate_external_ssl_cert(
        ips=[external_rest_host, internal_rest_host],
        cn=external_rest_host,
        cert_path=config[NGINX]['external_cert_path'],
        key_path=config[NGINX]['external_key_path']
    )


def _create_certs():
    # Needs to be run here, because openssl is required and is
    # installed by nginx
    common.remove(constants.SSL_CERTS_TARGET_DIR)
    common.mkdir(constants.SSL_CERTS_TARGET_DIR)

    logger.info('Creating CA certificate...')
    certificates.generate_ca_cert()

    internal_rest_host = config[NGINX]['internal_rest_host']
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


def _start_and_verify_service():
    logger.info('Starting NGINX service...')
    systemd.enable(NGINX, append_prefix=False)
    systemd.restart(NGINX, append_prefix=False)
    systemd.verify_alive(NGINX, append_prefix=False)

    # TODO: See if it's OK to remove this part
    # logger.info('Verifying NGINX service is up...')
    # nginx_url = 'https://127.0.0.1:{0}/api/v2.1/version'.format(
    #     config[NGINX]['internal_rest_port'])
    # response = check_http_response(nginx_url)
    # if response.code not in (200, 401):
    #     raise StandardError('Could not verify Nginx service is alive')


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
    logger.notice('NGINX installed successfully')


def configure():
    logger.notice('Configuring NGINX...')
    _configure()
    logger.notice('NGINX configured successfully')

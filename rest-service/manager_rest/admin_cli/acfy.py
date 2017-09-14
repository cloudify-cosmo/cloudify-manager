import os
import yaml
import click
from functools import wraps

from . import helptexts, logger


CLICK_CONTEXT_SETTINGS = dict(
    help_option_names=['-h', '--help'],
    token_normalize_func=lambda param: param.lower())


SSL_CERTS_TARGET_DIR = '/etc/cloudify/ssl'
CERT_METADATA_FILE_PATH = os.path.join(SSL_CERTS_TARGET_DIR,
                                       'certificate_metadata')
INTERNAL_SSL_CA_CERT_FILENAME = 'cloudify_internal_ca_cert.pem'
INTERNAL_SSL_CA_KEY_FILENAME = 'cloudify_internal_ca_key.pem'
INTERNAL_CA_CERT_PATH = os.path.join(SSL_CERTS_TARGET_DIR,
                                     INTERNAL_SSL_CA_CERT_FILENAME)
INTERNAL_CA_KEY_PATH = os.path.join(SSL_CERTS_TARGET_DIR,
                                    INTERNAL_SSL_CA_KEY_FILENAME)
INTERNAL_SSL_CERT_FILENAME = 'cloudify_internal_cert.pem'
INTERNAL_SSL_KEY_FILENAME = 'cloudify_internal_key.pem'
INTERNAL_CERT_PATH = os.path.join(SSL_CERTS_TARGET_DIR,
                                  INTERNAL_SSL_CERT_FILENAME)
INTERNAL_KEY_PATH = os.path.join(SSL_CERTS_TARGET_DIR,
                                 INTERNAL_SSL_KEY_FILENAME)


def pass_context(func):
    """Make click context Cloudify specific

    This exists purely for aesthetic reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.pass_context(func)


def pass_logger(func):
    """Simply passes the logger to a command."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        new_logger = logger.get_logger()
        return func(logger=new_logger, *args, **kwargs)
    return wrapper


def group(name):
    """Allow to create a group with a default click context
    and a cls for click's `didyoueamn` without having to repeat
    it for every group.
    """
    return click.group(name=name, context_settings=CLICK_CONTEXT_SETTINGS)


def command(*args, **kwargs):
    """Make Click commands Cloudify specific

    This exists purely for aesthetical reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.command(*args, **kwargs)


def argument(*args, **kwargs):
    """Make Click arguments Cloudify specific

    This exists purely for aesthetic reasons, otherwise
    Some decorators are called `@click.something` instead of
    `@cfy.something`
    """
    return click.argument(*args, **kwargs)


def show_version(ctx, param, value):
    if value:
        logger.get_logger().info('version')
        ctx.exit()


class Options(object):
    def __init__(self):
        self.version = click.option(
            '--version',
            is_flag=True,
            callback=show_version,
            expose_value=False,
            is_eager=True,
            help=helptexts.VERSION)
        self.node_name = click.option(
            '--node-name',
            help=helptexts.NODE_NAME)
        self.host_ip = click.option(
            '--host-ip',
            help=helptexts.HOST_IP)
        self.manager_username = click.option(
            '-u',
            '--manager-username',
            required=False,
            help=helptexts.MANAGER_USERNAME
        )
        self.manager_password = click.option(
            '-p',
            '--manager-password',
            required=False,
            help=helptexts.MANAGER_PASSWORD)
        self.master_ip = click.option(
            '-m',
            '--master-ip',
            required=True,
            help=helptexts.MASTER_IP)
        self.with_manager_deployment = click.option(
            '--with-manager-deployment/--without-manager-deployment',
            help=helptexts.WITH_MANAGER_DEPLOYMENT)
        self.parameters = click.option(
            '-p',
            '--parameters',
            type=click.File('rb'),
            callback=lambda ctx, param, value: yaml.load(value))
        self.ca_cert_path = click.option(
            '--ca-cert',
            default=INTERNAL_CA_CERT_PATH,
            type=click.Path())
        self.ca_key_path = click.option(
            '--ca-key',
            default=INTERNAL_CA_KEY_PATH,
            type=click.Path())
        self.internal_cert_path = click.option(
            '--internal-cert',
            default=INTERNAL_CERT_PATH,
            type=click.Path())
        self.internal_key_path = click.option(
            '--internal-key',
            default=INTERNAL_KEY_PATH,
            type=click.Path())

    @staticmethod
    def verbose(expose_value=False):
        return click.option(
            '-v',
            '--verbose',
            count=True,
            expose_value=expose_value,
            is_eager=True,
            help=helptexts.VERBOSE)

    @staticmethod
    def ldap_server():
        return click.option(
            '-s',
            '--ldap-server',
            required=True,
            help=helptexts.LDAP_SERVER)

    @staticmethod
    def ldap_username():
        return click.option(
            '-u',
            '--ldap-username',
            required=True,
            help=helptexts.LDAP_USERNAME)

    @staticmethod
    def ldap_password():
        return click.option(
            '-p',
            '--ldap-password',
            required=True,
            help=helptexts.LDAP_PASSWORD)

    @staticmethod
    def ldap_domain():
        return click.option(
            '-d',
            '--ldap-domain',
            required=False,
            help=helptexts.LDAP_DOMAIN)

    @staticmethod
    def ldap_is_active_directory():
        return click.option(
            '-a',
            '--ldap-is-active-directory',
            required=False,
            is_flag=True,
            default=False,
            help=helptexts.LDAP_IS_ACTIVE_DIRECTORY)

    @staticmethod
    def ldap_dn_extra():
        return click.option(
            '-e',
            '--ldap-dn-extra',
            required=False,
            help=helptexts.LDAP_DN_EXTRA)


options = Options()

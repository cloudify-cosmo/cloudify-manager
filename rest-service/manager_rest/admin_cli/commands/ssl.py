import os
import json
import socket
import tempfile
import subprocess
from contextlib import contextmanager

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


def _load_cert_metadata():
    try:
        with open(acfy.CERT_METADATA_FILE_PATH) as f:
            return json.load(f)
    except IOError:
        return {}


def _store_cert_metadata(internal_rest_host, networks=None):
    metadata = _load_cert_metadata()
    metadata['internal_rest_host'] = internal_rest_host
    if networks is not None:
        metadata['networks'] = networks
    with open(acfy.CERT_METADATA_FILE_PATH, 'w'):
        json.dump(metadata, acfy.CERT_METADATA_FILE_PATH)


CSR_CONFIG_TEMPLATE = """
[req]
distinguished_name = req_distinguished_name
req_extensions = server_req_extensions
[ server_req_extensions ]
subjectAltName={metadata}
[ req_distinguished_name ]
commonName = _common_name # ignored, _default is used instead
commonName_default = {cn}
"""


def _format_ips(ips):
    altnames = set(ips)

    # Ensure we trust localhost
    altnames.add('127.0.0.1')
    altnames.add('localhost')

    subject_altdns = [
        'DNS:{name}'.format(name=name)
        for name in altnames
    ]
    subject_altips = []
    for name in altnames:
        ip_address = False
        try:
            socket.inet_pton(socket.AF_INET, name)
            ip_address = True
        except socket.error:
            # Not IPv4
            pass
        try:
            socket.inet_pton(socket.AF_INET6, name)
            ip_address = True
        except socket.error:
            # Not IPv6
            pass
        if ip_address:
            subject_altips.append('IP:{name}'.format(name=name))

    cert_metadata = ','.join([
        ','.join(subject_altdns),
        ','.join(subject_altips),
    ])
    return cert_metadata


@contextmanager
def _csr_config(cn, metadata):
    with tempfile.NamedTemporaryFile(delete=False) as conf_file:
        conf_file.write(CSR_CONFIG_TEMPLATE.format(cn=cn, metadata=metadata))

    try:
        yield conf_file.name
    finally:
        os.unlink(conf_file.name)


def _generate_ssl_certificate(ips,
                              cn,
                              cert_path,
                              key_path,
                              sign_cert=acfy.INTERNAL_CA_CERT_PATH,
                              sign_key=acfy.INTERNAL_CA_KEY_PATH):
    cert_metadata = _format_ips(ips)

    csr_path = '{0}.csr'.format(cert_path)

    with _csr_config(cn, cert_metadata) as conf_path:
        subprocess.check_call([
            'openssl', 'req',
            '-newkey', 'rsa:2048',
            '-nodes',
            '-batch',
            '-config', conf_path,
            '-out', csr_path,
            '-keyout', key_path,
        ])
        x509_command = [
            'openssl', 'x509',
            '-days', '3650',
            '-req', '-in', csr_path,
            '-extfile', conf_path,
            '-out', cert_path,
            '-extensions', 'server_req_extensions',
        ]
        if sign_cert and sign_key:
            x509_command += [
                '-CA', sign_cert,
                '-CAkey', sign_key,
                '-CAcreateserial'
            ]
        else:
            x509_command += [
                '-signkey', key_path
            ]
        subprocess.check_call(x509_command)
        os.unlink(csr_path)
    return cert_path, key_path


@ssl.command(name='create-internal-certs')
@acfy.options.host_ip
@acfy.options.ca_cert_path
@acfy.options.ca_key_path
@acfy.options.internal_cert_path
@acfy.options.internal_key_path
@acfy.pass_logger
def create_internal_certs(host_ip, ca_cert, ca_key,
                          internal_cert, internal_key, logger):
    metadata = _load_cert_metadata()
    networks = metadata.get('networks', {})
    internal_rest_host = host_ip or metadata['internal_rest_host']
    networks['default'] = internal_rest_host
    cert_ips = [internal_rest_host] + list(networks.values())
    _generate_ssl_certificate(cert_ips, internal_rest_host, internal_cert,
                              internal_key, sign_cert=ca_cert,
                              sign_key=ca_key)
    logger.info('Generated SSL certificate: {0} and key: {1}'.format(
        internal_cert, internal_key
    ))
    logger.info('Restarting nginx and RabbitMQ...')
    subprocess.check_call(['systemctl', 'restart', 'nginx',
                           'cloudify-rabbitmq'])
    logger.info('Done!')

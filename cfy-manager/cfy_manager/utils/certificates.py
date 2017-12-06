#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import argh
import json
import socket
from os.path import join
from contextlib import contextmanager

from .common import sudo, remove, chown
from .files import write_to_file, write_to_tempfile

from ..logger import get_logger
from .. import constants as const

logger = get_logger('Certificates')


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


def store_cert_metadata(internal_rest_host,
                        networks=None,
                        filename=const.CERT_METADATA_FILE_PATH):
    metadata = load_cert_metadata()
    metadata['internal_rest_host'] = internal_rest_host
    if networks is not None:
        metadata['networks'] = networks
    write_to_file(metadata, filename, json_dump=True)
    chown(const.CLOUDIFY_USER, const.CLOUDIFY_GROUP, filename)


def load_cert_metadata(filename=const.CERT_METADATA_FILE_PATH):
    try:
        with open(filename) as f:
            return json.load(f)
    except IOError:
        return {}


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


@contextmanager
def _csr_config(cn, metadata):
    """Prepare a config file for creating a ssl CSR.

    :param cn: the subject commonName
    :param metadata: string to use as the subjectAltName, should be formatted
                     like "IP:1.2.3.4,DNS:www.com"
    """
    csr_config = CSR_CONFIG_TEMPLATE.format(cn=cn, metadata=metadata)
    temp_config_path = write_to_tempfile(csr_config)

    try:
        yield temp_config_path
    finally:
        remove(temp_config_path)


def _generate_ssl_certificate(ips,
                              cn,
                              cert_path,
                              key_path,
                              sign_cert=None,
                              sign_key=None):
    """Generate a public SSL certificate and a private SSL key

    :param ips: the ips (or names) to be used for subjectAltNames
    :type ips: List[str]
    :param cn: the subject commonName for the new certificate
    :type cn: str
    :param cert_path: path to save the new certificate to
    :type cert_path: str
    :param key_path: path to save the key for the new certificate to
    :type key_path: str
    :param sign_cert: path to the signing cert (self-signed by default)
    :type sign_cert: str
    :param sign_key: path to the signing cert's key (self-signed by default)
    :type sign_key: str
    :return: The path to the cert and key files on the manager
    """
    # Remove duplicates from ips
    subject_altnames = _format_ips(ips)
    logger.debug(
        'Generating SSL certificate {0} and key {1} with subjectAltNames: {2}'
        .format(cert_path, key_path, subject_altnames)
    )

    csr_path = '{0}.csr'.format(cert_path)

    with _csr_config(cn, subject_altnames) as conf_path:
        sudo([
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
            '-out', cert_path,
            '-extensions', 'server_req_extensions',
            '-extfile', conf_path
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
        sudo(x509_command)
        remove(csr_path)

    logger.debug('Generated SSL certificate: {0} and key: {1}'.format(
        cert_path, key_path
    ))
    return cert_path, key_path


def generate_internal_ssl_cert(ips, cn):
    return _generate_ssl_certificate(
        ips,
        cn,
        const.INTERNAL_CERT_PATH,
        const.INTERNAL_KEY_PATH,
        sign_cert=const.CA_CERT_PATH,
        sign_key=const.CA_KEY_PATH
    )


def generate_external_ssl_cert(ips, cn):
    return _generate_ssl_certificate(
        ips,
        cn,
        const.EXTERNAL_CERT_PATH,
        const.EXTERNAL_KEY_PATH
    )


def generate_ca_cert():
    sudo([
        'openssl', 'req',
        '-x509',
        '-nodes',
        '-newkey', 'rsa:2048',
        '-days', '3650',
        '-batch',
        '-out', const.CA_CERT_PATH,
        '-keyout', const.CA_KEY_PATH
    ])
    # PKCS12 file required for riemann due to JVM
    # While we don't really want the private key in there, not having it
    # causes failures
    # The password is also a bit pointless here since it's in the same place
    # as a readable copy of the certificate and if this path can be written to
    # maliciously then all is lost already.
    pkcs12_path = join(
        const.SSL_CERTS_TARGET_DIR,
        const.INTERNAL_PKCS12_FILENAME
    )
    sudo([
        'openssl', 'pkcs12', '-export',
        '-out', pkcs12_path,
        '-in', const.CA_CERT_PATH,
        '-inkey', const.CA_KEY_PATH,
        '-password', 'pass:cloudify',
    ])
    logger.debug('Generated CA certificate: {0} and key: {1}'.format(
        const.CA_CERT_PATH, const.CA_KEY_PATH
    ))


@argh.arg('--metadata',
          help='File containing the cert metadata. It should be a '
          'JSON file containing an object with the '
          '"internal_rest_host" and "networks" fields.')
@argh.arg('--manager-ip', help='The IP of this machine on the default network')
def create_internal_certs(manager_ip=None,
                          metadata=const.CERT_METADATA_FILE_PATH):
    """
    Recreate Cloudify Manager's internal certificates, based on the manager IP
    and a metadata file input
    """
    cert_metadata = load_cert_metadata(filename=metadata)
    internal_rest_host = manager_ip or cert_metadata['internal_rest_host']

    networks = cert_metadata.get('networks', {})
    networks['default'] = internal_rest_host
    cert_ips = [internal_rest_host] + list(networks.values())
    generate_internal_ssl_cert(
        ips=cert_ips,
        cn=internal_rest_host
    )
    store_cert_metadata(
        internal_rest_host,
        networks,
        filename=metadata
    )


@argh.arg('--private-ip', help="The manager's private IP", required=True)
@argh.arg('--public-ip', help="The manager's public IP", required=True)
@argh.arg('--sign-cert', help="Path to the signing cert "
                              "(self-signed by default)")
@argh.arg('--sign-key', help="Path to the signing cert's key "
                             "(self-signed by default)")
def create_external_certs(private_ip=None,
                          public_ip=None,
                          sign_cert=None,
                          sign_key=None):
    """
    Recreate Cloudify Manager's external certificates, based on the public
    and private IPs
    """
    # Note: the function has default values for the IP arguments, but they
    # are actually required by argh, so it won't be possible to call this
    # function without them from the CLI
    _generate_ssl_certificate(
        ips=[public_ip, private_ip],
        cn=public_ip,
        cert_path=const.EXTERNAL_CERT_PATH,
        key_path=const.EXTERNAL_KEY_PATH,
        sign_cert=sign_cert,
        sign_key=sign_key
    )

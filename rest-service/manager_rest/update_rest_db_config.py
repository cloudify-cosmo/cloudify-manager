#!/opt/manager/env/bin/python

import argparse
import grp
import json
import logging
import os
import pwd
import re
import shutil
import sys
import yaml


def _copy_ca_cert():
    """Copy the DB CA cert from the haproxy dir to cfyuser's dir.

    Also chown to cfyuser.
    """
    ca_cert = '/etc/cloudify/ssl/db_ca.crt'
    shutil.copyfile('/etc/haproxy/ca.crt', ca_cert)
    logging.info('Copied the CA certificate to %s', ca_cert)

    cfyuser_uid = pwd.getpwnam('cfyuser').pw_uid
    cfyuser_gid = grp.getgrnam('cfyuser').gr_gid
    os.chown(ca_cert, cfyuser_uid, cfyuser_gid)
    return ca_cert


def _find_db_servers(haproxy_cfg):
    """Parse the haproxy config

    :param haproxy_cfg: file object containing the haproxy config
    :return: list of database server addresses
    """
    config_content = haproxy_cfg.read()
    logging.debug('Loaded haproxy config: %d bytes', len(config_content))
    server_lines = re.findall(
        r'server postgresql_.*$', config_content, re.MULTILINE)
    server_addrs = [line.split()[2] for line in server_lines]
    logging.info('Found %d servers in the haproxy config', len(server_lines))
    logging.debug('DB servers: %s', server_addrs)
    return [addr.partition(':')[0] for addr in server_addrs]


def update_db_address(restservice_config_path, commit):
    logging.debug('Loading haproxy config...')
    try:
        with open('/etc/haproxy/haproxy.cfg') as f:
            dbs = _find_db_servers(f)
    except IOError as e:
        raise RuntimeError('Cannot open HAProxy config: {0}'.format(e))

    logging.debug('Loading restservice config')
    with open(restservice_config_path) as f:
        rest_config = yaml.safe_load(f)
    logging.debug('Loaded restservice config')

    rest_config['postgresql_ca_cert_path'] = _copy_ca_cert()
    rest_config['postgresql_host'] = dbs

    serialized = json.dumps(rest_config, indent=4, sort_keys=True)
    print(serialized)
    if commit:
        with open(restservice_config_path, 'w') as f:
            f.write(serialized)
        logging.info('Stored the new config in %s', restservice_config_path)
    else:
        logging.info('Dry-run: did not store the new config')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Rewrite RESTservice db config to not use HAProxy")
    parser.add_argument(
        '--restservice-config-path',
        default='/opt/manager/cloudify-rest.conf')
    parser.add_argument('--commit', action='store_true',
                        help='Commit changes, otherwise dryrun')

    parser.add_argument('--verbose', '-v', action='count', default=0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(levelname)s %(asctime)s %(message)s',
                        stream=sys.stderr)
    if os.geteuid() != 0:
        raise RuntimeError('This script must be run as root!')
    update_db_address(args.restservice_config_path, args.commit)

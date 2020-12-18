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


def _copy(src, dest, username, groupname):
    """Copy src to dest and chown to uid:gid"""
    shutil.copyfile(src, dest)
    uid = pwd.getpwnam(username).pw_uid
    gid = grp.getgrnam(groupname).gr_gid
    os.chown(dest, uid, gid)
    return dest


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


def _format_db_urls(rest_config, params, db):
    params = '&'.join('{0}={1}'.format(k, v) for k, v in params.items() if v)
    for host in rest_config['postgresql_host']:
        yield (
            'postgres://{username}:{password}@{host}:{port}/{db}?{params}'
            .format(
                username=rest_config['postgresql_username'],
                password=rest_config['postgresql_password'],
                host=host,
                port=5432,
                db=db,
                params=params
            )
        )


def _update_stage_conf(rest_config, commit):
    logging.debug('Loading stage config...')
    try:
        with open('/opt/cloudify-stage/conf/app.json') as f:
            stage_conf = json.load(f)
    except IOError as e:
        raise RuntimeError('Cannot open Stage config: {0}'.format(e))

    postgres_ca = '/opt/cloudify-stage/conf/postgres_ca.crt'
    if commit:
        _copy(
            rest_config['postgresql_ca_cert_path'],
            postgres_ca,
            'stage_user',
            'cfyuser'
        )
    stage_conf['db']['options']['dialectOptions'].update({
        'ssl': {
            'rejectUnauthorized': True,
            'ca': postgres_ca
        }
    })
    if rest_config.get('postgresql_ssl_key_path'):
        postgres_cert = '/opt/cloudify-stage/conf/postgres.crt'
        postgres_key = '/opt/cloudify-stage/conf/postgres.key'
        if commit:
            _copy(
                rest_config['postgresql_ssl_cert_path'],
                postgres_cert,
                'stage_user',
                'cfyuser'
            )
            _copy(
                rest_config['postgresql_ssl_key_path'],
                postgres_key,
                'stage_user',
                'cfyuser'
            )
        stage_conf['db']['options']['dialectOptions']['ssl'].update({
            'cert': postgres_cert,
            'key': postgres_key,
        })
    else:
        postgres_cert = None
        postgres_key = None

    url_params = {
        'sslcert': postgres_cert,
        'sslkey': postgres_key,
        'sslmode': 'verify-full',
        'sslrootcert': postgres_ca
    }
    stage_conf['db']['url'] = list(_format_db_urls(
        rest_config, url_params, db='stage'))
    serialized = json.dumps(stage_conf, indent=4, sort_keys=True)
    logging.info('Stage config:')
    print(serialized)
    if commit:
        with open('/opt/cloudify-stage/conf/app.json', 'w') as f:
            f.write(serialized)


def _update_composer_conf(rest_config, commit):
    logging.debug('Loading composer config...')
    try:
        with open('/opt/cloudify-composer/backend/conf/prod.json') as f:
            composer_conf = json.load(f)
    except IOError as e:
        raise RuntimeError('Cannot open Composer config: {0}'.format(e))

    postgres_ca = '/opt/cloudify-composer/backend/conf/postgres_ca.crt'
    if commit:
        _copy(
            rest_config['postgresql_ca_cert_path'],
            postgres_ca,
            'composer_user',
            'cfyuser'
        )
    composer_conf['db']['options']['dialectOptions'].update({
        'ssl': {
            'rejectUnauthorized': True,
            'ca': postgres_ca
        }
    })
    if rest_config.get('postgresql_ssl_key_path'):
        postgres_cert = '/opt/cloudify-composer/backend/conf/postgres.crt'
        postgres_key = '/opt/cloudify-composer/backend/conf/postgres.key'
        if commit:
            _copy(
                rest_config['postgresql_ssl_cert_path'],
                postgres_cert,
                'composer_user',
                'cfyuser'
            )
            _copy(
                rest_config['postgresql_ssl_key_path'],
                postgres_key,
                'composer_user',
                'cfyuser'
            )
        composer_conf['db']['options']['dialectOptions']['ssl'].update({
            'cert': postgres_cert,
            'key': postgres_key,
        })
    else:
        postgres_cert = None
        postgres_key = None

    url_params = {
        'sslcert': postgres_cert,
        'sslkey': postgres_key,
        'sslmode': 'verify-full',
        'sslrootcert': postgres_ca
    }
    composer_conf['db']['url'] = list(_format_db_urls(
        rest_config, url_params, db='composer'))
    serialized = json.dumps(composer_conf, indent=4, sort_keys=True)
    logging.info('Composer config:')
    print(serialized)
    if commit:
        with open('/opt/cloudify-composer/backend/conf/prod.json', 'w') as f:
            f.write(serialized)


def update_db_address(restservice_config_path, commit):
    logging.debug('Loading haproxy config...')
    try:
        with open('/etc/haproxy/haproxy.cfg') as f:
            dbs = _find_db_servers(f)
    except IOError:
        logging.info('Cannot open HAProxy config: nothing to do')
        return

    if not dbs:
        logging.info("No DB addresses configured, nothing to do")
        return

    logging.debug('Loading restservice config')
    with open(restservice_config_path) as f:
        rest_config = yaml.safe_load(f)
    logging.debug('Loaded restservice config')

    db_ca = '/etc/cloudify/ssl/db_ca.crt'
    rest_config['postgresql_ca_cert_path'] = db_ca
    if commit:
        _copy(
            '/etc/haproxy/ca.crt',
            db_ca,
            'cfyuser',
            'cfyuser'
        )
    rest_config['postgresql_host'] = dbs

    _update_stage_conf(rest_config, commit)
    _update_composer_conf(rest_config, commit)

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

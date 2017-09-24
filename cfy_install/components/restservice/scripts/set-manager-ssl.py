#!/usr/bin/env python

import argparse
import subprocess


DEFAULT_CONF_PATH = '/etc/nginx/conf.d/default.conf'
HTTP_PATH = '/etc/nginx/conf.d/http-external-rest-server.cloudify'
HTTPS_PATH = '/etc/nginx/conf.d/https-external-rest-server.cloudify'


parser = argparse.ArgumentParser()
parser.add_argument('--ssl-enabled', dest='ssl', action='store_true')
parser.add_argument('--ssl-disabled', dest='ssl', action='store_false')
parser.set_defaults(ssl=True)


def set_nginx_ssl(enabled):
    with open(DEFAULT_CONF_PATH) as f:
        config = f.read()
    if enabled:
        config = config.replace(HTTP_PATH, HTTPS_PATH)
    else:
        config = config.replace(HTTPS_PATH, HTTP_PATH)
    with open(DEFAULT_CONF_PATH, 'w') as f:
        f.write(config)


def restart_nginx():
    # wait one second before restarting nginx so that the caller has a chance
    # to clean up (this is most likely to be called from the REST service)
    subprocess.check_call([
        '/usr/bin/systemd-run', '--on-active=1s',
        '--timer-property=AccuracySec=100ms',
        '/usr/bin/systemctl', 'restart', 'nginx'
    ])


if __name__ == '__main__':
    args = parser.parse_args()
    set_nginx_ssl(args.ssl)
    restart_nginx()

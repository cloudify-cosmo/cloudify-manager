
# This script has to run using the Python executable found in:
# /opt/mgmtworker/env/bin/python in order to properly load the manager
# blueprints utils.py module.

import logging
import sys

import utils


class CtxWithLogger(object):
    logger = logging.getLogger('internal-ssl-certs-logger')


utils.ctx = CtxWithLogger()


if __name__ == '__main__':
    cert_metadata = utils.load_cert_metadata()
    if len(sys.argv) == 2:
        internal_rest_host = sys.argv[1]
    else:
        internal_rest_host = cert_metadata['internal_rest_host']

    networks = cert_metadata.get('networks', {})
    cert_ips = [internal_rest_host] + list(networks.values())
    utils.generate_internal_ssl_cert(ips=cert_ips, name=internal_rest_host)
    utils.store_cert_metadata(internal_rest_host)

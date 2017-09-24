
# This script has to run using the Python executable with which
# the bootstrap was performed (the one that has cfy_install in it)

import sys

from cfy_install.utils import certificates


if __name__ == '__main__':
    cert_metadata = certificates.load_cert_metadata()
    if len(sys.argv) == 2:
        internal_rest_host = sys.argv[1]
    else:
        internal_rest_host = cert_metadata['internal_rest_host']

    networks = cert_metadata.get('networks', {})
    networks['default'] = internal_rest_host
    cert_ips = [internal_rest_host] + list(networks.values())
    certificates.generate_internal_ssl_cert(
        ips=cert_ips,
        name=internal_rest_host
    )
    certificates.store_cert_metadata(internal_rest_host, networks)

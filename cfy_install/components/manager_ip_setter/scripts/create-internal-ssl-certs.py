# This script has to run using the Python executable with which
# the bootstrap was performed (the one that has cfy_install in it)

import argparse

from cfy_install.utils import certificates
from cfy_install.constants import CERT_METADATA_FILE_PATH


parser = argparse.ArgumentParser()
parser.add_argument('--metadata', default=CERT_METADATA_FILE_PATH,
                    help='File containing the cert metadata. It should be a '
                         'JSON file containing an object with the '
                         '"internal_rest_host" and "networks" fields.')
parser.add_argument('manager_ip', default=None, nargs='?',
                    help='The IP of this machine on the default network')


if __name__ == '__main__':
    args = parser.parse_args()
    cert_metadata = certificates.load_cert_metadata(filename=args.metadata)
    internal_rest_host = args.manager_ip or cert_metadata['internal_rest_host']

    networks = cert_metadata.get('networks', {})
    networks['default'] = internal_rest_host
    cert_ips = [internal_rest_host] + list(networks.values())
    certificates.generate_internal_ssl_cert(
        ips=cert_ips,
        cn=internal_rest_host
    )
    certificates.store_cert_metadata(
        internal_rest_host,
        networks,
        filename=args.metadata
    )

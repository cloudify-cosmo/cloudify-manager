
import json

from os import environ as env

from base64 import urlsafe_b64encode
from cloudify_rest_client.client import CloudifyClient


def run_test():
    try:
        manager_ip = env['manager_ip']
        url_version_postfix = env['url_version_postfix']
        rest_client = _get_rest_client(manager_ip)
        rest_client_url = rest_client._client.url
        expected_rest_client_url = 'http://{0}:80{1}'.format(
            manager_ip, url_version_postfix)
        if rest_client_url == expected_rest_client_url:
            return {
                'failed': False,
                'details': rest_client.manager.get_status()
            }
        else:
            return {
                'failed': True,
                'details': 'rest client url is {0} instead of {1}'.format(
                    rest_client_url, expected_rest_client_url)
            }
    except Exception as e:
        return {
            'failed': True,
            'details': str(e)
        }


def _get_rest_client(manager_ip):
    creds = '{0}:{1}'.format(env['manager_user'], env['manager_password'])
    headers = {
        'Authorization': 'Basic {0}'.format(urlsafe_b64encode(creds)),
        'Tenant': env['manager_tenant']
    }
    return CloudifyClient(host=manager_ip, headers=headers)


if __name__ == '__main__':
    out = run_test()
    with open(env['result_path'], 'w') as f:
        json.dump(out, f)

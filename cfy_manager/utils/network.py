import os
import socket
import base64
import urllib2
from time import sleep
from tempfile import mkstemp
from urlparse import urlparse

from ..exceptions import NetworkError
from ..components.service_names import MANAGER

from .common import run
from ..config import config
from ..logger import get_logger

logger = get_logger('Network')


def is_url(url):
    return urlparse(url).scheme != ''


def is_port_open(port, host='localhost'):
    """Try to connect to (host, port), return if the port was listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    return sock.connect_ex((host, port)) == 0


def wait_for_port(port, host='localhost'):
    """Helper function to wait for a port to open before continuing"""
    counter = 1

    logger.info('Waiting for {0}:{1} to become available...'.format(
        host, port))

    for tries in range(24):
        if not is_port_open(port, host=host):
            logger.info(
                '{0}:{1} is not available yet, retrying... '
                '({2}/24)'.format(host, port, counter))
            sleep(2)
            counter += 1
            continue
        logger.info('{0}:{1} is open!'.format(host, port))
        return
    raise NetworkError(
        'Failed to connect to {0}:{1}...'.format(host, port)
    )


def curl_download(source, destination=None):
    """Download file using the curl command.

    :param source: Source URL for the file to download
    :typ source: str
    :param destination:
        Path to the directory where the file should be downloaded.
        If none is provided, a temp file will be used
    :type destination: str

    """
    if not destination:
        suffix = '.{0}'.format(source.split('.')[-1])
        fd, destination = mkstemp(suffix=suffix)
        os.close(fd)
        config.add_temp_path_to_clean(destination)

    curl_cmd = [
        'curl',
        '--silent',
        '--show-error',
        '--location', source,
        '--create-dir',
        '--output', destination,
    ]
    logger.info('Downloading: {0} into {1}'.format(source, destination))
    run(curl_cmd)
    return destination


def get_auth_headers():
    security = config[MANAGER]['security']
    username = security['admin_username']
    password = security['admin_password']
    return {
        'Authorization': 'Basic ' + base64.b64encode('{0}:{1}'.format(
            username, password)
        ),
        'tenant': 'default_tenant'
    }


def check_http_response(url, **request_kwargs):
    req = urllib2.Request(url, **request_kwargs)
    try:
        response = urllib2.urlopen(req)
    except urllib2.HTTPError as e:
        # HTTPError can also be used as a non-200 response. Pass this
        # through to the predicate function, so it can decide if a
        # non-200 response is fine or not.
        response = e

    return response

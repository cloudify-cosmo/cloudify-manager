#!/bin/python/env

import os
import sys
import shlex
import logging
import subprocess
from time import sleep
from requests import get
from requests.auth import HTTPBasicAuth

from cloudify_rest_client import CloudifyClient

logging_format = 'DOCKER-CFY-AGENT: %(asctime)s - ' \
                 '%(name)s - %(levelname)s - %(message)s'
logging.basicConfig(stream=sys.stdout,
                    level=logging.DEBUG,
                    format=logging_format)

WORK_DIR = '/root'
AGENT_DOWNLOAD_SCRIPT = '{dir}/download_and_install_agent.sh'.format(
    dir=WORK_DIR)
MANAGER = os.environ.get('MANAGER', '172.20.0.2')
USERNAME = os.environ.get('USERNAME', 'admin')
PASSWORD = os.environ.get('PASSWORD', 'admin')
TENANT = os.environ.get('TENANT', 'default_tenant')
NODE_INSTANCE_ID = os.environ['NODE_INSTANCE_ID']
AGENT_SSL_DIR = '{0}/{1}/cloudify/ssl/'.format(WORK_DIR, NODE_INSTANCE_ID)
AGENT_CONFIG_MESSAGE = 'Agent config created. ' \
                       'To configure/start the agent, ' \
                       'download the following script'
CERT_PATH = '{0}/cloudify_internal_cert.pem'.format(AGENT_SSL_DIR)


def execute_shell_command(command,
                          stdout=subprocess.PIPE,
                          stderr=None,
                          stdin=None):

    popen_args = {
        'args': shlex.split(command),
        'stdout': stdout,
    }
    if stderr:
        popen_args['stderr'] = stderr
    if stdin:
        popen_args['stdin'] = stdin
    logging.info('Starting executing {0}'.format(popen_args))
    process = subprocess.Popen(**popen_args)
    output, error = process.communicate()
    logging.info(output)
    logging.info(error)
    logging.info('Finished executing.')
    return output, error


def download_and_write(url, path):
    logging.info('Downloading {0} to {1}'.format(url, path))
    res = get(
        url,
        headers={'Tenant': TENANT},
        auth=HTTPBasicAuth(USERNAME, PASSWORD),
        verify=False,
        stream=True
    )
    logging.info('Got the URL content, now we will write it to a file.')
    f = open(path, 'wb')
    f.write(res.content)
    f.close()


if __name__ == "__main__":

    logging.info(
        'Starting Cloudify Agent Discovery process for provided Agent.')
    agent_running = False
    client = CloudifyClient(
        host=MANAGER,
        username=USERNAME,
        password=PASSWORD,
        tenant=TENANT,
        trust_all=True
    )

    # We use a loop to keep the Docker container running.
    # We want to poll the deployment for a log message that
    # has the URL for the agent download package.
    # That's the mechanism in place for using provided agent.
    while True:
        sleep(5)
        if agent_running:
            logging.info('Agent is running...{0}'.format(
                execute_shell_command('ps -ef')))
            continue
        events = client.events.list(include_logs=True)
        for event in events:
            if AGENT_CONFIG_MESSAGE not in event['message']:
                continue
            logging.debug(event)
            if NODE_INSTANCE_ID in event['node_instance_id']:
                logging.info(
                    'We have an event for our node instance: {0}'.format(
                        event))
                url = event['message'].split(' ')[-1]
                if url.startswith('https') and url.endswith('.sh'):
                    download_and_write(url, AGENT_DOWNLOAD_SCRIPT)
                    execute_shell_command(
                        'chmod u+x {0}'.format(AGENT_DOWNLOAD_SCRIPT))
                    execute_shell_command('mkdir -p {0}'.format(AGENT_SSL_DIR))
                    execute_shell_command(
                        'sh -c {0}'.format(AGENT_DOWNLOAD_SCRIPT))
                    agent_running = True

logging.info('EXITING SCRIPT - Shoudn\'t happen.')

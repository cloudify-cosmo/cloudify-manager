########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import json
import logging
import os
import shutil
import sys
import time
import tempfile
import threading
import unittest

import pika.exceptions
import sh

import cloudify.utils
import cloudify.logs
import cloudify.event
from cloudify_cli.colorful_event import ColorfulEvent

from testenv import utils
from testenv import docl
from testenv.services import postgresql

logger = cloudify.utils.setup_logger('TESTENV')
cloudify.utils.setup_logger('cloudify.rest_client', logging.INFO)

# Silencing 3rd party logs
for logger_name in ('sh', 'pika', 'requests.packages.urllib3.connectionpool'):
    cloudify.utils.setup_logger(logger_name, logging.WARNING)

testenv_instance = None


class BaseTestCase(unittest.TestCase):
    """
    A test case for cloudify integration tests.
    """

    def setUp(self):
        self.env = testenv_instance
        self.workdir = tempfile.mkdtemp(
            dir=self.env.test_working_dir,
            prefix='{0}-'.format(self._testMethodName))
        self.cfy = utils.get_cfy()
        self.addCleanup(shutil.rmtree, self.workdir, ignore_errors=True)
        self.logger = cloudify.utils.setup_logger(self._testMethodName,
                                                  logging.INFO)
        self.client = utils.create_rest_client()

    def tearDown(self):
        self.env.stop_dispatch_processes()

    @staticmethod
    def read_manager_file(file_path, no_strip=False):
        """
        Read a file from the cloudify manager filesystem.
        """
        return docl.read_file(file_path, no_strip=no_strip)

    @staticmethod
    def execute_on_manager(command, quiet=True):
        """
        Execute a shell command on the cloudify manager container.
        """
        return docl.execute(command, quiet)

    @staticmethod
    def copy_file_to_manager(source, target):
        """
        Copy a file to the cloudify manager filesystem

        """
        return docl.copy_file_to_manager(source=source, target=target)

    @staticmethod
    def get_plugin_data(plugin_name, deployment_id):
        """
        Retrieve the plugin state for a certain deployment.

        :param deployment_id: the deployment id in question.
        :param plugin_name: the plugin in question.
        :return: plugin data relevant for the deployment.
        :rtype dict
        """
        storage_file_path = os.path.join(
            testenv_instance.plugins_storage_dir,
            '{0}.json'.format(plugin_name)
        )
        if not os.path.exists(storage_file_path):
            return {}
        with open(storage_file_path, 'r') as f:
            data = json.load(f)
            if deployment_id not in data:
                data[deployment_id] = {}
            return data.get(deployment_id)

    @staticmethod
    def clear_plugin_data(plugin_name):
        """
        Clears plugin state.

        :param plugin_name: the plugin in question.
        """
        storage_file_path = os.path.join(
            testenv_instance.plugins_storage_dir,
            '{0}.json'.format(plugin_name)
        )
        if os.path.exists(storage_file_path):
            os.remove(storage_file_path)

    @staticmethod
    def do_assertions(assertions_func, timeout=10, **kwargs):
        return utils.do_retries(assertions_func,
                                timeout,
                                AssertionError,
                                **kwargs)

    @staticmethod
    def publish_riemann_event(deployment_id,
                              node_name,
                              node_id='',
                              host='localhost',
                              service='service',
                              state='',
                              metric=0,
                              ttl=60):
        event = {
            'host': host,
            'service': service,
            'state': state,
            'metric': metric,
            'time': int(time.time()),
            'node_name': node_name,
            'node_id': node_id,
            'ttl': ttl
        }
        queue = '{0}-riemann'.format(deployment_id)
        routing_key = deployment_id
        utils.publish_event(queue, routing_key, event)


class TestCase(BaseTestCase):

    def setUp(self):
        super(TestCase, self).setUp()
        utils.restore_provider_context()

    def tearDown(self):
        postgresql.reset_data()
        super(TestCase, self).tearDown()


class AgentTestCase(BaseTestCase):

    def tearDown(self):
        logger.info('Removing leftover test containers')
        docl.clean(label=['marker=test', self.env.env_label])
        super(AgentTestCase, self).tearDown()

    def read_host_file(self, file_path, deployment_id, node_id):
        """
        Read a file from a dockercompute node instance container filesystem.
        """
        runtime_props = self._get_runtime_properties(
            deployment_id=deployment_id, node_id=node_id)
        container_id = runtime_props['container_id']
        return docl.read_file(file_path, container_id=container_id)

    def get_host_ip(self, deployment_id, node_id):
        """
        Get the ip of a dockercompute node instance container.
        """
        runtime_props = self._get_runtime_properties(
            deployment_id=deployment_id, node_id=node_id)
        return runtime_props['ip']

    def get_host_key_path(self, deployment_id, node_id):
        """
        Get the the path on the manager container to the private key
        used to SSH into the dockercompute node instance container.
        """
        runtime_props = self._get_runtime_properties(
            deployment_id=deployment_id, node_id=node_id)
        return runtime_props['cloudify_agent']['key']

    def _get_runtime_properties(self, deployment_id, node_id):
        instance = self.client.node_instances.list(
            deployment_id=deployment_id,
            node_id=node_id)[0]
        return instance.runtime_properties


class BaseTestEnvironment(object):
    # See _build_resource_mapping
    mock_cloudify_agent = None

    def __init__(self, test_working_dir, env_label):
        self.test_working_dir = test_working_dir
        # A label is assigned to all containers started in the suite
        # (manager and dockercompute node instances)
        # This label is later used for cleanup purposes.
        self.env_label = env_label
        self.plugins_storage_dir = os.path.join(
            self.test_working_dir, 'plugins-storage')
        self.maintenance_folder = os.path.join(
            self.test_working_dir, 'maintenance')
        os.makedirs(self.plugins_storage_dir)
        self.amqp_events_printer_thread = threading.Thread(
            target=self.amqp_events_printer)
        self.amqp_events_printer_thread.daemon = True

    def create(self):
        logger.info('Setting up test environment... workdir=[{0}]'
                    .format(self.test_working_dir))
        os.environ['CFY_WORKDIR'] = self.test_working_dir
        try:
            logger.info('Starting manager container')
            docl.run_manager(
                label=[self.env_label],
                resources=self._build_resource_mapping())
            cfy = utils.get_cfy()
            cfy.use(utils.get_manager_ip())
            self.amqp_events_printer_thread.start()
        except:
            self.destroy()
            raise

    def _build_resource_mapping(self):
        """
        This function builds a list of resources to mount on the manager
        container. Each entry is composed of the source directory on the host
        machine (the client) and where it should be mounted on the container.
        """

        # The plugins storage dir is mounted as a writable shared directory
        # between all containers and the host machine. Most mock plugins make
        # use of a utility method in mock_plugins.utils.update_storage to save
        # state that the test can later read.
        resources = [{
            'src': self.plugins_storage_dir,
            'dst': '/opt/integration-plugin-storage',
            'write': True
        }]

        # Import only for the sake of finding the module path on the file
        # system
        import mock_plugins
        import fasteners
        mock_plugins_dir = os.path.dirname(mock_plugins.__file__)
        fasteners_dir = os.path.dirname(fasteners.__file__)

        # All code directories will be mapped to the management worker
        # virtualenv and will also be included in the custom agent package
        # created in the test suite setup
        code_directories = [
            # Plugins import mock_plugins.utils.update_storage all over the
            # place
            mock_plugins_dir,

            # mock_plugins.utils.update_storage makes use of the fasteners
            # library
            fasteners_dir
        ]

        # All plugins under mock_plugins are mapped. These are mostly used
        # as operations and workflows mapped in the different tests blueprints.
        code_directories += [
            os.path.join(mock_plugins_dir, directory)
            for directory in os.listdir(mock_plugins_dir)
        ]

        for directory in code_directories:
            basename = os.path.basename(directory)

            # Only map directories (skips __init__.py and utils.py)
            if not os.path.isdir(directory):
                continue

            # In the AgentlessTestEnvironment cloudify_agent is mocked
            # So we override the original cloudify_agent. In the
            # AgentTestEnvironment the real cloudify agent is used
            # so we skip the override
            if basename == 'cloudify_agent' and not self.mock_cloudify_agent:
                continue

            # Each code directory is mounted in two places:
            # 1. The management worker virtualenv
            # 2. /opt/agent-template is a directory created by docl that
            #    contains an extracted CentOS agent package.
            #    in the AgentTestEnvironment setup, we override the CentOS
            #    package with the content of this directory using the
            #    `docl build-agent` command.
            for dst in ['/opt/mgmtworker/env/lib/python2.7/site-packages/{0}'.format(basename),       # noqa
                        '/opt/agent-template/env/lib/python2.7/site-packages/{0}'.format(basename)]:  # noqa
                resources.append({'src': directory, 'dst': dst})
        return resources

    def destroy(self):
        logger.info('Destroying test environment...')
        os.environ.pop('CFY_WORKDIR', None)
        docl.clean(label=[self.env_label])
        self.delete_working_directory()

    def delete_working_directory(self):
        if os.path.exists(self.test_working_dir):
            logger.info('Deleting test environment from: %s',
                        self.test_working_dir)
            shutil.rmtree(self.test_working_dir, ignore_errors=True)

    @classmethod
    def stop_dispatch_processes(cls):
        logger.info('Shutting down all dispatch processes')
        try:
            docl.execute('pkill -9 -f cloudify/dispatch.py')
        except sh.ErrorReturnCode as e:
            if e.exit_code != 1:
                raise

    @staticmethod
    def amqp_events_printer():
        """
        This function will consume logs and events directly from the
        cloudify-logs and cloudify-events exchanges. (As opposed to the usual
        means of fetching events using the REST api).

        Note: This method is only used for events/logs printing.
        Tests that need to assert on event should use the REST client events
        module.
        """
        connection = utils.create_pika_connection()
        channel = connection.channel()
        exchanges = ['cloudify-events', 'cloudify-logs']
        queues = []
        for exchange in exchanges:
            channel.exchange_declare(exchange=exchange, type='fanout',
                                     auto_delete=True,
                                     durable=True)
            result = channel.queue_declare(exclusive=True)
            queue_name = result.method.queue
            queues.append(queue_name)
            channel.queue_bind(exchange=exchange, queue=queue_name)

        if not os.environ.get('CI'):
            cloudify.logs.EVENT_CLASS = ColorfulEvent
        cloudify.logs.EVENT_VERBOSITY_LEVEL = cloudify.event.MEDIUM_VERBOSE

        def callback(ch, method, properties, body):
            try:
                ev = json.loads(body)
                output = cloudify.logs.create_event_message_prefix(ev)
                if output:
                    sys.stdout.write('{0}\n'.format(output))
            except:
                logger.error('event/log format error - output: {0}'
                             .format(body), exc_info=True)

        channel.basic_consume(callback, queue=queues[0], no_ack=True)
        channel.basic_consume(callback, queue=queues[1], no_ack=True)
        try:
            channel.start_consuming()
        except pika.exceptions.ConnectionClosed:
            pass


class AgentlessTestEnvironment(BaseTestEnvironment):
    # See _build_resource_mapping
    mock_cloudify_agent = True


class AgentTestEnvironment(BaseTestEnvironment):
    # See _build_resource_mapping
    mock_cloudify_agent = False

    def create(self):
        super(AgentTestEnvironment, self).create()
        try:
            logger.info('Installing docker on manager container (if required)')
            # Installing docker (only the docker client is used) on the manager
            # container (docl will only try installing docker if it isn't
            # already installed).
            docl.install_docker()
            # docl will override the CentOS agent package with the content of
            # /opt/agent-template. See _build_resource_mapping
            docl.build_agent()
            self._copy_docker_conf_file()
        except:
            self.destroy()
            raise

    def _copy_docker_conf_file(self):
        # the docker_conf.json file is used to pass information
        # to the dockercompute plugin. (see mock_plugins/dockercompute)
        docl.execute('mkdir -p /root/dockercompute')
        with tempfile.NamedTemporaryFile() as f:
            json.dump({
                # The dockercompute plugin needs to know where to find the
                # docker host
                'docker_host': docl.docker_host(),

                # Used to know from where to mount the plugins storage dir
                # on dockercompute node instances containers
                'plugins_storage_dir': self.plugins_storage_dir,

                # Used for cleanup purposes
                'env_label': self.env_label
            }, f)
            f.flush()
            docl.copy_file_to_manager(
                source=f.name,
                target='/root/dockercompute/docker_conf.json')


def create_env(env_cls):
    global testenv_instance
    top_level_dir = os.path.join(tempfile.gettempdir(),
                                 'cloudify-integration-tests')
    env_label = cloudify.utils.id_generator(4)
    env_name = 'WorkflowsTests-{0}'.format(env_label)
    test_working_dir = os.path.join(top_level_dir, env_name)
    os.makedirs(test_working_dir)
    testenv_instance = env_cls(test_working_dir, 'env={0}'.format(env_label))
    testenv_instance.create()


def destroy_env():
    testenv_instance.destroy()

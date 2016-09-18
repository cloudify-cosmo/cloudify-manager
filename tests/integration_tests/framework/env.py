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
import tempfile
from contextlib import contextmanager

import sh

import cloudify.utils
import cloudify.logs
import cloudify.event

from integration_tests.framework import constants, docl, utils
from integration_tests.framework.amqp_events_printer import EventsPrinter


logger = cloudify.utils.setup_logger('TESTENV')
cloudify.utils.setup_logger('cloudify.rest_client', logging.INFO)

# Silencing 3rd party logs
for logger_name in ('sh', 'pika', 'requests.packages.urllib3.connectionpool'):
    cloudify.utils.setup_logger(logger_name, logging.WARNING)

instance = None


class BaseTestEnvironment(object):
    # See _build_resource_mapping
    mock_cloudify_agent = None

    def __init__(self, test_working_dir, env_id):
        sh.ErrorReturnCode.truncate_cap = 1024 * 1024
        self.test_working_dir = test_working_dir
        self.env_id = env_id
        # A label is assigned to all containers started in the suite
        # (manager and dockercompute node instances)
        # This label is later used for cleanup purposes.
        self.env_label = 'env={0}'.format(self.env_id)
        self.plugins_storage_dir = os.path.join(
            self.test_working_dir, 'plugins-storage')
        self.maintenance_folder = os.path.join(
            self.test_working_dir, 'maintenance')
        os.makedirs(self.plugins_storage_dir)
        self.amqp_events_printer_thread = None
        # This is used by tests/framework when a repository is fetched from
        # github. For example, the hello world repo or the plugin template.
        self.core_branch_name = os.environ.get(constants.BRANCH_NAME_CORE,
                                               'master')

    def start_events_printer(self):
        self.amqp_events_printer_thread = EventsPrinter()
        self.amqp_events_printer_thread.start()

    def create_environment(self):
        logger.info('Setting up test environment... workdir=[{0}]'
                    .format(self.test_working_dir))
        os.environ['CFY_WORKDIR'] = self.test_working_dir
        try:
            kwargs = {}
            if not os.environ.get('CI'):
                kwargs['enable_colors'] = True
            cfy = utils.get_cfy()
            cfy.init(**kwargs)
            docl.init(resources=self._build_resource_mapping())
            self.on_environment_created()
        except:
            self.destroy()
            raise

    def on_environment_created(self):
        raise NotImplementedError

    def run_manager(self, tag=None, label=None):
        logger.info('Starting manager container')
        docl.run_manager(label=([self.env_label] + list(label or [])),
                         tag=tag)
        self.on_manager_created()

    def on_manager_created(self):
        cfy = utils.get_cfy()
        kwargs = {}
        rest_port = os.environ.get(constants.CLOUDIFY_REST_PORT)
        if rest_port:
            kwargs = {'rest_port': rest_port}
        cfy.use(utils.get_manager_ip(),
                manager_user='root',
                manager_key=docl.ssh_key_path(),
                **kwargs)
        self.start_events_printer()

    def _build_resource_mapping(self):
        """
        This function builds a list of resources to mount on the manager
        container. Each entry is composed of the source directory on the host
        machine (the client) and where it should be mounted on the container.
        """

        # The plugins storage dir is mounted as a writable shared directory
        # between all containers and the host machine. Most mock plugins make
        # use of a utility method in
        # integration_tests_plugins.utils.update_storage to save state that the
        # test can later read.
        resources = [{
            'src': self.plugins_storage_dir,
            'dst': '/opt/integration-plugin-storage',
            'write': True
        }]

        # Import only for the sake of finding the module path on the file
        # system
        import integration_tests_plugins
        import fasteners
        plugins_dir = os.path.dirname(integration_tests_plugins.__file__)
        fasteners_dir = os.path.dirname(fasteners.__file__)

        # All code directories will be mapped to the management worker
        # virtualenv and will also be included in the custom agent package
        # created in the test suite setup
        code_directories = [
            # Plugins import integration_tests_plugins.utils.update_storage
            # all over the place
            plugins_dir,

            # integration_tests_plugins.utils.update_storage makes use of the
            # fasteners library
            fasteners_dir
        ]

        # All plugins under integration_tests_plugins are mapped. These are
        # mostly used as operations and workflows mapped in the different tests
        # blueprints.
        code_directories += [
            os.path.join(plugins_dir, directory)
            for directory in os.listdir(plugins_dir)
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


class AgentlessTestEnvironment(BaseTestEnvironment):
    # See _build_resource_mapping
    mock_cloudify_agent = True

    def on_environment_created(self):
        self.run_manager()


class AgentTestEnvironment(BaseTestEnvironment):
    # See _build_resource_mapping
    mock_cloudify_agent = False

    def on_environment_created(self):
        self.run_manager()

    def on_manager_created(self):
        super(AgentTestEnvironment, self).on_manager_created()
        logger.info('Installing docker on manager container (if required)')
        # Installing docker (only the docker client is used) on the manager
        # container (docl will only try installing docker if it isn't
        # already installed).
        docl.install_docker()
        # docl will override the CentOS agent package with the content of
        # /opt/agent-template. See _build_resource_mapping
        docl.build_agent()
        self._copy_docker_conf_file()

    def _copy_docker_conf_file(self):
        # the docker_conf.json file is used to pass information
        # to the dockercompute plugin. (see
        # integration_tests_plugins/dockercompute)
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


class ManagerTestEnvironment(AgentTestEnvironment):

    def on_environment_created(self):
        pass

    def prepare_bootstrappable_container(self,
                                         label=None,
                                         additional_exposed_ports=None):
        with docl.update_config(
                additional_expose=additional_exposed_ports):
            self.prepared_inputs = docl.prepare_bootstrappable_container(
                label=[self.env_label] + list((label or [])))

    def bootstrap_prepared_container(self, inputs=None, label=None,
                                     modify_blueprint_func=None,
                                     additional_exposed_ports=None):
        inputs = inputs or {}
        inputs.update(self.prepared_inputs)
        logger.info('Bootstrapping manager on a new container')
        test_manager_blueprint_path = None
        if modify_blueprint_func:
            test_manager_blueprint_path = \
                self._handle_modify_blueprint_func(modify_blueprint_func)
        with self.update_config(
                manager_blueprint_path=test_manager_blueprint_path,
                additional_exposed_ports=additional_exposed_ports):
            docl.bootstrap_prepared_container(inputs=inputs)
        tag = 'integration-tests/{0}'.format(self.env_id)
        docl.save_image(tag=tag)
        self.run_manager(tag=tag, label=label)

    def _handle_modify_blueprint_func(self, modify_blueprint_func):
        manager_blueprint_path = docl.simple_manager_blueprint_path()
        manager_blueprint_dir = os.path.dirname(manager_blueprint_path)
        test_manager_blueprint_dir = os.path.join(
            self.test_working_dir, 'test-manager-blueprint')
        if os.path.isdir(test_manager_blueprint_dir):
            shutil.rmtree(test_manager_blueprint_dir)
        shutil.copytree(manager_blueprint_dir, test_manager_blueprint_dir)
        test_manager_blueprint_path = os.path.join(
            test_manager_blueprint_dir,
            os.path.basename(manager_blueprint_path))
        with utils.YamlPatcher(test_manager_blueprint_path) as patcher:
            modify_blueprint_func(patcher, test_manager_blueprint_dir)
        return test_manager_blueprint_path

    def clean_manager(self, label=None, clean_tag=False):
        docl.clean(label=[self.env_label] + list((label or [])))
        if clean_tag:
            tag = 'integration-tests/{0}'.format(self.env_id)
            try:
                logger.info('Removing container image {0}'.format(tag))
                docl.remove_image(tag=tag)
            except sh.ErrorReturnCode:
                logger.warn(
                    'Failed removing container image {0}. This most likely '
                    'means the image never got created in the first place'
                    .format(tag))

    @contextmanager
    def update_config(self,
                      additional_exposed_ports=None,
                      manager_blueprint_path=None):
        with docl.update_config(additional_expose=additional_exposed_ports,
                                manager_blueprint_path=manager_blueprint_path):
            yield


def create_env(env_cls):
    global instance
    top_level_dir = os.path.join(tempfile.gettempdir(),
                                 'cloudify-integration-tests')
    env_id = cloudify.utils.id_generator(4).lower()
    env_name = 'WorkflowsTests-{0}'.format(env_id)
    test_working_dir = os.path.join(top_level_dir, env_name)
    os.makedirs(test_working_dir)
    instance = env_cls(test_working_dir, env_id)
    instance.create_environment()


def destroy_env():
    instance.destroy()

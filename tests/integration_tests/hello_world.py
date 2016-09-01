#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
import tarfile

import nose.tools
import requests


from integration_tests import utils
from integration_tests.utils import deploy_application as deploy

_HELLO_WORLD_URL = 'https://github.com/cloudify-cosmo/{0}/archive/{1}.tar.gz'


class _HelloWorld(object):
    """Used by AgentTestCase and OwnManagerTestCase"""

    def __init__(self,
                 test_case,
                 use_cli,
                 modify_blueprint_func,
                 skip_uninstall):
        self.test_case = test_case
        self.use_cli = use_cli
        self.modify_blueprint_func = modify_blueprint_func
        self.skip_uninstall = skip_uninstall

    @nose.tools.nottest
    def test_hello_world(self):
        blueprint_file = self._prepare_hello_world()
        deployment, _ = deploy(blueprint_file, timeout_seconds=120)

        self._assert_hello_world_events(deployment.id)
        self._assert_hello_world_metric(deployment.id)

        ip = self.test_case.get_host_ip(node_id='vm',
                                        deployment_id=deployment.id)
        url = 'http://{0}:8080'.format(ip)

        def _webserver_request():
            return requests.get(url, timeout=1)

        # assert webserver running
        response = utils.do_retries(
            _webserver_request,
            exception_class=requests.exceptions.ConnectionError)
        self.test_case.assertIn('http_web_server', response.text)

        if not self.skip_uninstall:
            utils.undeploy_application(deployment.id)

            # assert webserver not running
            self.test_case.assertRaises(requests.exceptions.ConnectionError,
                                        _webserver_request)

        return deployment

    def _assert_hello_world_events(self, deployment_id):
        rest_client = utils.create_rest_client()
        events = rest_client.events.list(
            deployment_id=deployment_id)
        self.test_case.assertGreater(len(events.items), 0)

    def _assert_hello_world_metric(self, deployment_id):
        influx_client = utils.create_influxdb_client()
        try:
            # select monitoring events for deployment from
            # the past 5 seconds. a NameError will be thrown only if NO
            # deployment events exist in the DB regardless of time-span
            # in query.
            influx_client.query('select * from /^{0}\./i '
                                'where time > now() - 5s'
                                .format(deployment_id))
        except NameError as e:
            self.test_case.fail(
                'monitoring events list for deployment with ID {0} were '
                'not found on influxDB. error is: {1}'
                .format(deployment_id, e))

    def _prepare_hello_world(self):
        logger = self.test_case.logger
        repo_name = 'cloudify-hello-world-example'
        branch = self.test_case.env.core_branch_name
        workdir = self.test_case.env.test_working_dir
        blueprint_tar = os.path.join(workdir, 'hello.tar.gz')
        blueprint_dir = os.path.join(workdir, '{0}-{1}'.format(repo_name,
                                                               branch))
        blueprint_file = os.path.join(blueprint_dir,
                                      'dockercompute_blueprint.yaml')

        if not os.path.exists(blueprint_dir):
            logger.info('Downloading hello world tar')
            helloworld_url = _HELLO_WORLD_URL.format(repo_name, branch)
            response = requests.get(helloworld_url, stream=True)
            with open(blueprint_tar, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            with tarfile.open(blueprint_tar, 'r:gz') as tar:
                tar.extractall(path=workdir)
            shutil.copy(
                utils.get_resource('dockercompute_helloworld/blueprint.yaml'),
                blueprint_file)
            shutil.copy(
                utils.get_resource('dsl/plugins/diamond.yaml'),
                os.path.join(blueprint_dir, 'diamond.yaml'))
            shutil.copy(
                utils.get_resource('dsl/plugins/dockercompute.yaml'),
                os.path.join(blueprint_dir, 'dockercompute.yaml'))
        else:
            logger.info('Reusing existing hello world tar')

        if self.modify_blueprint_func:
            new_blueprint_dir = os.path.join(self.test_case.workdir,
                                             'test-hello-world')
            if os.path.isdir(new_blueprint_dir):
                shutil.rmtree(new_blueprint_dir)
            shutil.copytree(blueprint_dir, new_blueprint_dir)
            blueprint_dir = new_blueprint_dir
            blueprint_file = os.path.join(blueprint_dir,
                                          'dockercompute_blueprint.yaml')
            with utils.YamlPatcher(blueprint_file) as patcher:
                self.modify_blueprint_func(patcher, blueprint_dir)

        return blueprint_file


def test_hello_world(test_case, use_cli, modify_blueprint_func,
                     skip_uninstall):
    # TODO, actually implement the use_cli part
    return _HelloWorld(
        test_case=test_case,
        use_cli=use_cli,
        modify_blueprint_func=modify_blueprint_func,
        skip_uninstall=skip_uninstall).test_hello_world()

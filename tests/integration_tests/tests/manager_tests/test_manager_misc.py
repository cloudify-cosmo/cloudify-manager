########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import tarfile
import tempfile
from contextlib import closing

import requests
import sh

from integration_tests import ManagerTestCase
from integration_tests import utils


class MiscManagerTest(ManagerTestCase):

    def test_cfy_logs(self):
        self.run_manager()
        self.logger.info('Testing `cfy logs download`')
        with tempfile.NamedTemporaryFile() as tempf:
            self.cfy.logs.download(output_path=tempf.name)
            with closing(tarfile.open(name=tempf.name)) as tar:
                files = [f.name for f in tar.getmembers()]
                self.assertIn('cloudify/journalctl.log', files)
                self.assertIn('cloudify/nginx/cloudify.access.log', files)
                self.logger.info('Success!')

        self.logger.info('Testing `cfy logs backup`')
        self.cfy.logs.backup(verbose=True)
        output = self.execute_on_manager('ls /var/log')
        self.assertIn('cloudify-manager-logs_', output)

        self.logger.info('Testing `cfy logs purge`')
        self.cfy.logs.purge(force=True)
        self.execute_on_manager(
            'test ! -s /var/log/cloudify/nginx/cloudify.access.log')

    def test_tmux_session(self):
        self.run_manager()
        self.logger.info('Test list without tmux installed...')
        try:
            self.cfy.ssh(list_sessions=True)
        except sh.ErrorReturnCode_1 as ex:
            self.assertIn('tmux executable not found on manager', ex.stdout)

        self.logger.info('Installing tmux...')
        self.execute_on_manager('yum install tmux -y')

        self.logger.info('Test listing sessions when non are available..')
        output = self.cfy.ssh(list_sessions=True)
        self.assertIn('No sessions are available', output)

        self.logger.info('Test running ssh command...')
        content = 'yay'
        remote_path = '/tmp/ssh_test_output_file'
        self.cfy.ssh(command='echo {0} > {1}'.format(content, remote_path))
        self.assertEqual(content, self.read_manager_file(remote_path))

    def test_no_es_clustering(self):
        """Tests that when bootstrapping we don't cluster two elasticsearch
        nodes.

        This test mainly covers the use case where a user bootstraps two
        managers on the same network.

        The test runs two nodes on the same machine. If they're not clustered,
        two nodes on different servers will definitely not be clustered.
        """
        with self.env.update_config(additional_exposed_ports=[9201]):
            self.run_manager()
            self.logger.info('Duplicating elasticsearch config...')
            self.execute_on_manager('mkdir /etc/es_test')
            self.execute_on_manager('cp /etc/elasticsearch/elasticsearch.yml '
                                    '/etc/es_test/es.yml')

            self.logger.info('Replacing ES REST port for second node...')
            sed_cmd = ('sed -i -e "s/http.port: 9200/http.port: 9201/" '
                       '/etc/es_test/es.yml')
            self.execute_on_manager(sed_cmd)

            self.logger.info('Running second node...')
            es_cmd = ('/usr/share/elasticsearch/bin/elasticsearch '
                      '-Des.pidfile=/var/run/elasticsearch/es_test.pid '
                      '-Des.default.path.home=/usr/share/elasticsearch '
                      '-Des.default.path.logs=/var/log/elasticsearch '
                      '-Des.default.path.data=/var/lib/elasticsearch '
                      '-Des.default.config=/etc/es_test/es.yml '
                      '-Des.default.path.conf=/etc/es_test')
            with tempfile.NamedTemporaryFile() as f:
                f.write('nohup {0} >& /dev/null < /dev/null &'.format(es_cmd))
                f.flush()
                self.copy_file_to_manager(f.name, '/etc/es_test/run.sh')
            self.execute_on_manager('bash /etc/es_test/run.sh')

            node1_url = 'http://{0}:9200/_nodes'.format(utils.get_manager_ip())
            node2_url = 'http://{0}:9201/_nodes'.format(utils.get_manager_ip())

            def get_node_count_impl(url):
                return len(requests.get(url).json()['nodes'])

            def get_node_count(url):
                return utils.do_retries(get_node_count_impl, url=url,
                                        timeout_seconds=60)

            self.logger.info(
                'Verifying that both nodes are running but not clustered...')
            self.assertEqual(get_node_count(node1_url), 1)
            self.assertEqual(get_node_count(node2_url), 1)

    def test_logrotation(self):
        """Tests logrotation configuration on the manager.

        This goes over some of the logs but for each of services
        and performs logrotation based on the manager blueprint's provided
        logrotate configuration. It then validates that logrotation occurs.
        """
        self.run_manager()
        logs_dir = '/var/log/cloudify'
        test_log_files = [
            'elasticsearch/elasticsearch.log',
            'influxdb/log.txt',
            'mgmtworker/logs/test.log',
            'rabbitmq/rabbit@cloudifyman.log',
            'rest/cloudify-rest-service.log',
            'logstash/logstash.log',
            'nginx/cloudify.access.log',
            'riemann/riemann.log',
            'webui/backend.log'
        ]
        # the mgmtworker doesn't create a log file upon loading so we're
        # generating one for him.
        self.execute_on_manager(
            'touch /var/log/cloudify/mgmtworker/logs/test.log')

        self.logger.info('Cancelling date suffix on rotation...')
        sed_cmd = 'sed -i -e s/dateext/#dateext/ /etc/logrotate.conf'
        self.execute_on_manager(sed_cmd)

        self.logger.info('Installing crontab on manager')
        self.execute_on_manager('yum install -y cronie')

        def exists(path):
            try:
                self.execute_on_manager('test -f {0}'.format(path))
                return True
            except sh.ErrorReturnCode:
                return False

        for rotation in range(1, 9):
            for log_file in test_log_files:
                full_log_path = os.path.join(logs_dir, log_file)
                self.logger.info('fallocating 101M in {0}...'.format(
                    full_log_path))
                self.execute_on_manager(
                    'fallocate -l 101M {0}'.format(full_log_path))
                self.logger.info('Running cron.hourly to apply rotation...')
                self.execute_on_manager('run-parts /etc/cron.hourly')
                rotated_log_path = '{0}.{1}'.format(full_log_path, rotation)
                compressed_log_path = '{0}.gz'.format(rotated_log_path)
                if rotation == 8:
                    self.logger.info(
                        'Verifying overshot rotation did not occur: {0}...'
                        .format(compressed_log_path))
                    self.assertFalse(exists(compressed_log_path))
                elif rotation == 1:
                    self.logger.info(
                        'Verifying rotated log exists: {0}...'.format(
                            rotated_log_path))
                    self.assertTrue(exists(rotated_log_path))
                else:
                    self.logger.info(
                        'Verifying compressed log exists: {0}...'.format(
                            compressed_log_path))
                    self.assertTrue(exists(compressed_log_path))

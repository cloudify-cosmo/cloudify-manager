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

import sh
import os

from integration_tests import AgentlessTestCase


class MiscManagerTest(AgentlessTestCase):

    def test_logrotation(self):
        """Tests logrotation configuration on the manager.

        This goes over some of the logs but for each of services
        and performs logrotation based on the manager blueprint's provided
        logrotate configuration. It then validates that logrotation occurs.
        """
        logs_dir = '/var/log/cloudify'
        test_log_files = [
            'mgmtworker/mgmtworker.log',
            'mgmtworker/logs/test.log',
            'rabbitmq/rabbit@cloudifyman.log',
            'rest/cloudify-rest-service.log',
            'amqp-postgres/amqp_postgres.log',
            'nginx/cloudify.access.log',
            'composer/app.log'
        ]
        # the mgmtworker doesn't create a log file upon loading so we're
        # generating one for him.
        self.execute_on_manager('mkdir -p /var/log/cloudify/mgmtworker/logs')
        self.execute_on_manager(
            'touch /var/log/cloudify/mgmtworker/logs/test.log')

        self.logger.info('Cancelling date suffix on rotation...')
        # We need to do this separately for each logrotate configuration.
        for logrotate_cfg in ['cloudify-amqp-postgres',
                              'cloudify-mgmtworker',
                              'cloudify-rabbitmq',
                              'cloudify-composer',
                              'nginx',
                              'restservice']:
            self.logger.info('Cancelling for %s', logrotate_cfg)
            sed_cmd = 'sed -i -e s/dateext.*/nodateext/ /etc/logrotate.d/' \
                      '{}'.format(logrotate_cfg)
            self.execute_on_manager(sed_cmd)

        self.logger.info('Installing crontab on manager')
        self.execute_on_manager('yum install -y cronie')

        def exists(path):
            try:
                self.execute_on_manager('test -f {0}'.format(path))
                return True
            except sh.ErrorReturnCode:
                return False

        for rotation in range(1, 7):
            for log_file in test_log_files:
                full_log_path = os.path.join(logs_dir, log_file)
                self.logger.info('Allocating 101M in {0}...'.format(
                    full_log_path))
                self.execute_on_manager(
                    # Allocate 101 blocks of 1024Kb each (101M in total)
                    'dd if=/dev/zero of={0} bs=1024k count=101'
                    .format(full_log_path))
                self.logger.info('Running cron.daily to apply rotation...')
                self.execute_on_manager('run-parts /etc/cron.daily')
                rotated_log_path = '{0}.{1}'.format(full_log_path, rotation)
                compressed_log_path = '{0}.gz'.format(rotated_log_path)
                if rotation == 8:
                    self.logger.info(
                        'Verifying overshot rotation did not occur: {0}...'
                        .format(compressed_log_path))
                    self.assertFalse(exists(compressed_log_path))
                elif rotation == 1:
                    self.logger.info(
                        'Verifying rotated log exists: {0}... {1}'.format(
                            rotated_log_path, exists(rotated_log_path)))
                    self.assertTrue(exists(rotated_log_path))
                else:
                    self.logger.info(
                        'Verifying compressed log exists: {0}...'.format(
                            compressed_log_path))
                    self.assertTrue(exists(compressed_log_path))

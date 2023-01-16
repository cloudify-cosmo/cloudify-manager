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

import json
import os
import pytest
import textwrap

from integration_tests import AgentlessTestCase

pytestmark = pytest.mark.group_general


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
                    self.assertFalse(self.file_exists(compressed_log_path))
                elif rotation == 1:
                    does_exist = self.file_exists(rotated_log_path)
                    self.logger.info(
                        'Verifying rotated log exists: {0}... {1}'.format(
                            rotated_log_path, does_exist))
                    self.assertTrue(does_exist)
                else:
                    self.logger.info(
                        'Verifying compressed log exists: {0}...'.format(
                            compressed_log_path))
                    self.assertTrue(self.file_exists(compressed_log_path))

    def test_undeclared_permissions(self):
        """Check that all default permissions are declared.

        This test might fail after you add some new permissions to
        authorization.conf, and forget to add them to the default permissions
        list. Then, this will remind you.
        """
        permissions_source = self.execute_on_manager([
            '/opt/manager/env/bin/python',
            '-c',
            textwrap.dedent('''
                import json
                from manager_rest import permissions
                print(json.dumps(permissions.PERMISSIONS))
            ''')
        ])
        default_permissions = set(json.loads(permissions_source))
        existing_permission_names = {
            p['permission'] for p in self.client.permissions.list()
        }
        extra_permissions = existing_permission_names - default_permissions
        assert not extra_permissions, (
            "Some permissions declared in the default authorization.conf "
            "were not found in the default permissions list in restservice. "
            "Edit manager_rest/permissions.py, and add the new "
            f"permissions there: {extra_permissions}"
        )

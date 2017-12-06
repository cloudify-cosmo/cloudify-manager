#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from os.path import join

from .files import deploy
from .common import sudo, remove

from ..logger import get_logger
from ..constants import COMPONENTS_DIR
from ..exceptions import ValidationError

logger = get_logger('SystemD')


class SystemD(object):
    @staticmethod
    def systemctl(action, service='', retries=0, ignore_failure=False):
        systemctl_cmd = ['systemctl', action]
        if service:
            systemctl_cmd.append(service)
        return sudo(systemctl_cmd, retries=retries,
                    ignore_failures=ignore_failure)

    def configure(self, service_name, render=True, tmpfiles=False):
        """This configures systemd for a specific service.

        It requires that two files are present for each service one containing
        the environment variables and one containing the systemd config.
        All env files will be named "cloudify-SERVICENAME".
        All systemd config files will be named "cloudify-SERVICENAME.service".

        If `tmpfiles` is True, the directory
        `components/{service_name}/tmpfiles.d` must exist and contain the file
        `cloudify-{service_name}.config`. This will be deployed to
        `/usr/lib/tmpfiles.d`.
        """
        sid = 'cloudify-{0}'.format(service_name)
        env_dst = "/etc/sysconfig/{0}".format(sid)
        srv_dst = "/usr/lib/systemd/system/{0}.service".format(sid)

        service_dir_name = service_name.replace('-', '_')
        src_dir = join(COMPONENTS_DIR, service_dir_name, 'config')
        env_src = join(src_dir, sid)
        srv_src = join(src_dir, '{0}.service'.format(sid))
        tmp_src = join(src_dir, 'tmpfiles.d', '{0}.conf'.format(sid))

        logger.debug('Deploying systemd EnvironmentFile...')
        deploy(env_src, env_dst, render=render)
        logger.debug('Deploying systemd .service file...')
        deploy(srv_src, srv_dst, render=render)
        logger.debug('Enabling systemd .service...')
        self.systemctl('enable', '{0}.service'.format(sid))

        if tmpfiles:
            tmp_dst = "/usr/lib/tmpfiles.d/{0}.conf".format(sid)
            logger.debug('Deploying tmpfiles.d file...')
            deploy(tmp_src, tmp_dst, render=render)
            sudo(['systemd-tmpfiles', '--create'])

        self.systemctl('daemon-reload')

    def remove(self, service_name):
        """Stop and disable the service, and then delete its data
        """
        self.stop(service_name, ignore_failure=True)
        self.disable(service_name, ignore_failure=True)
        remove(self.get_service_file_path(service_name))
        remove(self.get_vars_file_path(service_name))

    @staticmethod
    def get_vars_file_path(service_name):
        """Returns the path to a systemd environment variables file
        for a given service_name. (e.g. /etc/sysconfig/cloudify-rabbitmq)
        """
        sid = 'cloudify-{0}'.format(service_name)
        return '/etc/sysconfig/{0}'.format(sid)

    @staticmethod
    def get_service_file_path(service_name):
        """Returns the path to a systemd service file
        for a given service_name.
        (e.g. /usr/lib/systemd/system/cloudify-rabbitmq.service)
        """
        sid = 'cloudify-{0}'.format(service_name)
        return "/usr/lib/systemd/system/{0}.service".format(sid)

    def enable(self, service_name, retries=0, append_prefix=True):
        full_service_name = self._get_full_service_name(service_name,
                                                        append_prefix)
        logger.debug('Enabling systemd service {0}...'.format(
            full_service_name))
        self.systemctl('enable', full_service_name, retries)

    def disable(self, service_name, retries=0, append_prefix=True,
                ignore_failure=False):
        full_service_name = self._get_full_service_name(service_name,
                                                        append_prefix)
        logger.debug('Disabling systemd service {0}...'.format(
            full_service_name))
        self.systemctl('disable', full_service_name, retries,
                       ignore_failure=ignore_failure)

    def start(self, service_name, retries=0, append_prefix=True):
        full_service_name = self._get_full_service_name(service_name,
                                                        append_prefix)
        logger.debug('Starting systemd service {0}...'.format(
            full_service_name))
        self.systemctl('start', full_service_name, retries)

    def stop(self, service_name, retries=0, append_prefix=True,
             ignore_failure=False):
        full_service_name = self._get_full_service_name(service_name,
                                                        append_prefix)
        logger.debug('Stopping systemd service {0}...'.format(
            full_service_name))
        self.systemctl('stop', full_service_name, retries,
                       ignore_failure=ignore_failure)

    def restart(self,
                service_name,
                retries=0,
                ignore_failure=False,
                append_prefix=True):
        full_service_name = self._get_full_service_name(service_name,
                                                        append_prefix)
        self.systemctl('restart', full_service_name, retries,
                       ignore_failure=ignore_failure)

    def is_alive(self, service_name, append_prefix=True):
        service_name = self._get_full_service_name(service_name, append_prefix)
        result = self.systemctl('status', service_name, ignore_failure=True)
        return result.returncode == 0

    def verify_alive(self, service_name, append_prefix=True):
        if self.is_alive(service_name, append_prefix):
            logger.debug('{0} is running'.format(service_name))
        else:
            raise ValidationError('{0} is not running'.format(service_name))

    @staticmethod
    def _get_full_service_name(service_name, append_prefix):
        if append_prefix:
            return 'cloudify-{0}'.format(service_name)
        return service_name


systemd = SystemD()

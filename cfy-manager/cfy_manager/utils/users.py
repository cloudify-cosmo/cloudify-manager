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

from pwd import getpwnam
from grp import getgrnam

from .common import sudo
from ..logger import get_logger

logger = get_logger('Users')


def _user_exists(user):
    logger.debug('Checking whether user {0} exists...'.format(user))
    try:
        getpwnam(user)
        logger.debug('User `{0}` already exists'.format(user))
        return True
    except KeyError:
        logger.debug('User `{0}` does not exist'.format(user))
        return False


def _group_exists(group):
    logger.debug('Checking whether group {0} exists...'.format(group))
    try:
        getgrnam(group)
        logger.debug('Group `{0}` already exists'.format(group))
        return True
    except KeyError:
        logger.debug('Group `{0}` does not exist'.format(group))
        return False


def create_service_user(user, group, home):
    """Creates a user.

    It will not create the home dir for it and assume that it already exists.
    This user will only be created if it didn't already exist.
    """

    if not _group_exists(group):
        logger.info('Creating group {group}'.format(group=group))
        # --force in groupadd causes it to return true if the group exists.
        # Other behaviour changes don't affect this basic use of the command.
        sudo(['groupadd', '--force', group])

    if not _user_exists(user):
        logger.info('Creating user {0}, home: {1}...'.format(user, home))
        sudo([
            'useradd',
            '--shell', '/sbin/nologin',
            '--home-dir', home, '--no-create-home',
            '--system',
            '--no-user-group',
            '--gid', group,
            user,
        ])


def delete_service_user(user):
    if user:
        sudo(['userdel', '--force', user], ignore_failures=True)


def delete_group(group):
    if group:
        sudo(['groupdel', group], ignore_failures=True)

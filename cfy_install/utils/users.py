from pwd import getpwnam

from .common import sudo
from ..logger import get_logger

logger = get_logger('Users')


def create_service_user(user, group, home):
    """Creates a user.

    It will not create the home dir for it and assume that it already exists.
    This user will only be created if it didn't already exist.
    """
    logger.info('Checking whether user {0} exists...'.format(user))
    try:
        getpwnam(user)
        logger.debug('User {0} already exists...'.format(user))
    except KeyError:
        logger.info('Creating group {group} if it does not exist'.format(
            group=group,
        ))
        # --force in groupadd causes it to return true if the group exists.
        # Other behaviour changes don't affect this basic use of the command.
        sudo(['groupadd', '--force', group])

        logger.info('Creating user {0}, home: {1}...'.format(
            user, home))
        sudo([
            'useradd',
            '--shell', '/sbin/nologin',
            '--home-dir', home, '--no-create-home',
            '--system',
            '--no-user-group',
            '--gid', group,
            user,
        ])

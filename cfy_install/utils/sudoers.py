from os.path import join

from .. import constants
from ..logger import get_logger

from .files import deploy
from .common import sudo, chmod, chown

logger = get_logger('sudoers')


def add_entry_to_sudoers(entry, description):
    # Comment out the description and add a N/L after the entry for visibility
    description = '# {0}'.format(description)
    entry = '{0}\n'.format(entry)

    for line in (description, entry, '#' * 60):
        # `visudo` handles sudoers file. Setting EDITOR to `tee -a` means that
        # whatever is piped should be appended to the file passed.
        sudo(['/sbin/visudo', '-f', constants.CLOUDIFY_SUDOERS_FILE],
             stdin=line, env={'EDITOR': '/bin/tee -a'})

    valid = sudo(
        ['visudo', '-cf', constants.CLOUDIFY_SUDOERS_FILE],
        ignore_failures=False,
    )
    if valid.returncode != 0:
        raise StandardError(
            "Generated sudoers entry containing \"{entry}\" was "
            "invalid.".format(entry=entry)
        )


def allow_user_to_sudo_command(full_command, description, allow_as='root'):
    entry = '{user}    ALL=({allow_as}) NOPASSWD:{full_command}'.format(
        user=constants.CLOUDIFY_USER,
        allow_as=allow_as,
        full_command=full_command
    )
    add_entry_to_sudoers(entry, description)


def deploy_sudo_command_script(
        script,
        description,
        component=None,
        allow_as='root',
        render=True
):
    # If passed a component, then script is a relative path, that needs to
    # be downloaded from the scripts folder. Otherwise, it's an absolute path
    if component:
        logger.debug('Deploying sudo script - {0}'.format(script))
        component_dir_name = component.replace('-', '_')
        src_dir = join(constants.COMPONENTS_DIR, component_dir_name, 'scripts')
        script_src = join(src_dir, script)
        script = join(constants.BASE_RESOURCES_PATH, component, script)
        deploy(script_src, script, render=render)
        chmod('550', script)
        chown('root', constants.CLOUDIFY_GROUP, script)

    logger.info('Allowing user `{0}` to run `{1}`'
                .format(constants.CLOUDIFY_USER, script))
    allow_user_to_sudo_command(
        full_command=script,
        description=description,
        allow_as=allow_as
    )

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

from .. import constants
from ..logger import get_logger
from ..exceptions import ValidationError

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
        raise ValidationError(
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

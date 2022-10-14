########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from cloudify.workflows import ctx
from .utils import sudo

NPM_BIN = os.path.join('/usr', 'bin', 'npm')


def run(command, app, user, *args):
    npm_command = [NPM_BIN, 'run', command]
    path_to_app = '/opt/cloudify-{0}/backend'.format(app)
    npm_command.extend(args)
    sudo(
        npm_command,
        cwd=path_to_app,
        user=user,
    )


def clear_db(app, user):
    """ Clear the App DB """
    ctx.logger.info('Clearing %s DB', app.capitalize())
    run('db-migrate-clear', app, user)


def downgrade_app_db(app, user, migration_version):
    """ Downgrade db schema, based on metadata from the snapshot """
    ctx.logger.info(
        'Downgrading %s DB to revision: %s', app.capitalize(),
        migration_version
    )
    run('db-migrate-down-to', app, user, migration_version)


def upgrade_app_db(app, user):
    """  Runs the migration up to latest revision """
    ctx.logger.info('Upgrading %s DB', app.capitalize())
    run('db-migrate', app, user)

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
from .utils import run as run_command

NPM_BIN = os.path.join('/opt', 'nodejs', 'bin', 'npm')


def run(command, *args):
    npm_command = [NPM_BIN, 'run', command]
    npm_command.extend(args)
    run_command(
        npm_command,
        cwd='/opt/cloudify-stage/backend',
    )


def clear_db():
    """ Clear the Stage DB """
    ctx.logger.info('Clearing Stage DB')
    run('db-migrate-clear')


def downgrade_stage_db(migration_version):
    """ Downgrade db schema, based on metadata from the snapshot """
    ctx.logger.info('Downgrading Stage DB to revision: {0}'
                    .format(migration_version))
    run('db-migrate-down-to', migration_version)


def upgrade_stage_db():
    """  Runs the migration up to latest revision """
    ctx.logger.info('Upgrading Stage DB')
    run('db-migrate')

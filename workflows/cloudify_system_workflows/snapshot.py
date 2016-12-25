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

from cloudify.workflows import ctx
from cloudify.decorators import workflow

from .snapshots.snapshot_create import SnapshotCreate
from .snapshots.snapshot_restore import SnapshotRestore


@workflow(system_wide=True)
def create(snapshot_id, config, **kwargs):
    ctx.logger.info('Creating snapshot `{0}`'.format(snapshot_id))

    include_metrics = kwargs.get('include_metrics', False)
    include_credentials = kwargs.get('include_credentials', False)
    create_snapshot = SnapshotCreate(
        snapshot_id,
        config,
        include_metrics,
        include_credentials
    )
    create_snapshot.create()


@workflow(system_wide=True)
def restore(snapshot_id,
            recreate_deployments_envs,
            config,
            force,
            timeout,
            tenant_name,
            premium_enabled,
            user_is_bootstrap_admin,
            **kwargs):
    ctx.logger.info('Restoring snapshot `{0}`'.format(snapshot_id))
    ctx.logger.debug('Restoring snapshot config: {0}'.format(config))

    restore_snapshot = SnapshotRestore(
        config,
        snapshot_id,
        recreate_deployments_envs,
        force,
        timeout,
        tenant_name,
        premium_enabled,
        user_is_bootstrap_admin
    )
    restore_snapshot.restore()

    ctx.logger.info('Successfully restored snapshot `{0}`'.format(snapshot_id))

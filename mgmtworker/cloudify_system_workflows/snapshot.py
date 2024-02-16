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

from cloudify.decorators import workflow
from cloudify.workflows import ctx
from cloudify_system_workflows.snapshots.utils import (
    is_split_services_environment,
)
from cloudify_system_workflows.snapshots.snapshot_create import SnapshotCreate
from cloudify_system_workflows.snapshots.snapshot_create_legacy import \
    LegacySnapshotCreate
from cloudify_system_workflows.snapshots.snapshot_restore import \
    SnapshotRestore


@workflow(system_wide=True)
def create(snapshot_id, config, **kwargs):
    ctx.logger.info('Creating snapshot `{0}`'.format(snapshot_id))

    include_credentials = kwargs.get('include_credentials', False)
    include_logs = kwargs.get('include_logs', True)
    include_events = kwargs.get('include_events', True)
    tempdir_path = kwargs.get('tempdir_path')
    legacy = kwargs.get('legacy', False)
    listener_timeout = kwargs.get('listener_timeout')
    if listener_timeout:
        listener_timeout = float(listener_timeout)

    if is_split_services_environment():
        # in k8s, we cannot create a legacy snapshot at all, because we have
        # no direct access to pg_dump and the postgres pod in general
        legacy = False

    if legacy:
        create_snapshot = LegacySnapshotCreate(
                snapshot_id,
                config,
                include_credentials,
                include_logs,
                include_events,
                tempdir_path,
        )
    else:
        create_snapshot = SnapshotCreate(
                snapshot_id,
                config,
                include_logs,
                include_events,
                listener_timeout,
        )
    create_snapshot.create()


@workflow(system_wide=True)
def restore(snapshot_id,
            config,
            force,
            timeout,
            restore_certificates,
            no_reboot,
            premium_enabled,
            user_is_bootstrap_admin,
            **kwargs):
    ctx.logger.info('Restoring snapshot `{0}`'.format(snapshot_id))
    ctx.logger.debug('Restoring snapshot config: {0}'.format(config))

    restore_snapshot = SnapshotRestore(
        config,
        snapshot_id,
        force,
        timeout,
        premium_enabled,
        user_is_bootstrap_admin,
        restore_certificates,
        no_reboot,
    )
    restore_snapshot.restore()

    ctx.logger.info('Successfully restored snapshot `{0}`'.format(snapshot_id))

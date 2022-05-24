import os
import shutil
import subprocess

from cloudify.manager import get_rest_client
from cloudify.workflows import ctx


def create(log_bundle_id, **kwargs):
    ctx.logger.info('Creating log bundle `{0}`'.format(log_bundle_id))
    try:
        client = get_rest_client(tenant=ctx.tenant_name)

        monitoring_username = client.manager.get_config(
            name='log_fetch_username')['value']
        monitoring_password = client.manager.get_config(
            name='log_fetch_password')['value']

        manager_nodes = {node['private_ip']
                         for node in client.manager.get_managers()}
        db_nodes = {node['host']
                    for node in client.manager.get_db_nodes()}
        broker_nodes = {node['management_host']
                        for node in client.manager.get_brokers()}
        addresses = manager_nodes | db_nodes | broker_nodes

        log_bundle_tmp_path = subprocess.check_output(
            [
                '/opt/mgmtworker/scripts/fetch-logs',
                '-a', ','.join(addresses),
            ],
            env={
                'MONITORING_USERNAME': monitoring_username,
                'MONITORING_PASSWORD': monitoring_password,
            },
            stderr=subprocess.STDOUT,
        ).strip()

        dest = f'/opt/manager/resources/log_bundles/{log_bundle_id}.zip'
        shutil.move(log_bundle_tmp_path, dest)
        os.chmod(dest, 0o440)
    except Exception as err:
        client.log_bundles.update_status(
            log_bundle_id,
            'failed',
            str(err),
        )
        raise
    client.log_bundles.update_status(log_bundle_id, 'created')

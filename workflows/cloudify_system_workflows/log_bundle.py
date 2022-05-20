import shutil
import subprocess

from cloudify.manager import get_rest_client
from cloudify.workflows import ctx


def create(log_bundle_id):
    ctx.logger.info('Creating log bundle `{0}`'.format(log_bundle_id))
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

    log_bundle_tmp_path = subprocess.check_call(
        [
            '/opt/mgmtworker/scripts/fetch_logs',
            '-a', ','.join(addresses),
        ],
        env={
            'MONITORING_USERNAME': monitoring_username,
            'MONITORING_PASSWORD': monitoring_password,
        },
        stderr=subprocess.STDOUT,
    )

    destination = f'/opt/manager/resources/log_bundles/{log_bundle_id}'
    shutil.move(log_bundle_tmp_path, destination)

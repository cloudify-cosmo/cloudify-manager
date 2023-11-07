import os
import pathlib
import subprocess

from cloudify.manager import get_rest_client
from cloudify.workflows import ctx
from cloudify_rest_client import CloudifyClient


def create(log_bundle_id, **kwargs):
    ctx.logger.info('Creating log bundle `{0}`'.format(log_bundle_id))
    try:
        client = get_rest_client(tenant=ctx.tenant_name)
        script_cmd, script_env = prepare_script(client)

        log_bundle_tmp_path = subprocess.check_output(
            script_cmd,
            env=script_env,
            stderr=subprocess.STDOUT,
        ).strip()

        client.log_bundles.upload_archive(log_bundle_id, log_bundle_tmp_path)
        os.remove(log_bundle_tmp_path)
    except Exception as err:
        client.log_bundles.update_status(
            log_bundle_id,
            'failed',
            str(err),
        )
        raise
    client.log_bundles.update_status(log_bundle_id, 'created')


def installation_method():
    match python_cmd():
        case "/opt/mgmtworker/env/bin/python3":
            return "rpm"
        case "/usr/local/bin/python":
            return "helm"
        case _:
            return "unknown"


def prepare_script(client: CloudifyClient) -> (list[str], dict[str, str]):
    manager_nodes = {
        node['private_ip'] for node in client.manager.get_managers()
    }
    db_nodes = {node['host'] for node in client.manager.get_db_nodes()}
    broker_nodes = {
        node['management_host'] for node in client.manager.get_brokers()
    }
    addresses = manager_nodes | db_nodes | broker_nodes

    match os.environ.get("RUNTIME_ENVIRONMENT").lower():
        case "k8s":
            installed_from = "helm"
        case "cluster" | "aio":
            installed_from = "rpm"
        case _:
            installed_from = installation_method()

    match installed_from:
        case "helm":
            script_cmd = ["/opt/mgmtworker/scripts/fetch-logs-local"]
            script_env = {}
        case "rpm":
            script_cmd = [
                "/opt/mgmtworker/scripts/fetch-logs-cluster",
                "-a",
                ",".join(addresses),
            ]
            script_env = {
                "MONITORING_USERNAME": client.manager.get_config(
                    name="log_fetch_username"
                )["value"],
                "MONITORING_PASSWORD": client.manager.get_config(
                    name="log_fetch_password"
                )["value"],
            }
        case _:
            raise RuntimeError(
                f"Unsupported installation method: {installed_from}"
            )
    return script_cmd, script_env


def python_cmd() -> str:
    for location in [
        "/opt/mgmtworker/env/bin/python3",
        "/usr/local/bin/python",
    ]:
        if pathlib.Path(location).is_file():
            return location

import os
from tempfile import NamedTemporaryFile, TemporaryDirectory

import requests

from cloudify.manager import get_rest_client
from cloudify.workflows import ctx
from cloudify.zip_utils import make_zip64_archive
from cloudify_rest_client import CloudifyClient

LOG_BASE_URL_LEGACY = "https://{server}:8009/cfylogs/"
LOG_CA_CERT_PATH_LEGACY = "/etc/cloudify/ssl/monitoring_ca_cert.pem"
LOG_PATH_K8S = "/opt/logs"


def create(log_bundle_id, **_):
    ctx.logger.info("Creating log bundle `{0}`".format(log_bundle_id))
    client = get_rest_client(tenant=ctx.tenant_name)
    try:
        log_bundle_tmp_path = do_create(client)
        client.log_bundles.upload_archive(log_bundle_id, log_bundle_tmp_path)
        os.remove(log_bundle_tmp_path)
    except Exception as err:
        client.log_bundles.update_status(
            log_bundle_id,
            "failed",
            str(err),
        )
        raise
    client.log_bundles.update_status(log_bundle_id, "created")


def do_create(client: CloudifyClient) -> str:
    manager_nodes = {
        node["private_ip"] for node in client.manager.get_managers()
    }
    db_nodes = {node["host"] for node in client.manager.get_db_nodes()}
    broker_nodes = {
        node["management_host"] for node in client.manager.get_brokers()
    }

    if os.environ.get("RUNTIME_ENVIRONMENT", "").lower() == "k8s":
        return fetch_k8s_logs()
    else:
        return fetch_legacy_logs(
            manager_nodes | db_nodes | broker_nodes,
            client.manager.get_config(name="log_fetch_username")["value"],
            client.manager.get_config(name="log_fetch_password")["value"],
        )


def fetch_k8s_logs() -> str:
    zip_file = NamedTemporaryFile(
        prefix="cfylogs", suffix=".zip", delete=False
    )
    zip_file.close()
    zip_path = zip_file.name
    make_zip64_archive(zip_path, LOG_PATH_K8S)
    return zip_path


def fetch_legacy_logs(
    addresses: set[str], username: str, password: str
) -> str:
    session = requests.Session()
    session.auth = (username, password)
    session.verify = LOG_CA_CERT_PATH_LEGACY

    with TemporaryDirectory(prefix="cfylogs") as temp_path:
        zip_file = NamedTemporaryFile(
            prefix="cfylogs", suffix=".zip", delete=False
        )
        zip_file.close()
        zip_path = zip_file.name

        for server in addresses:
            with open(
                os.path.join(temp_path, server + ".log"), "w"
            ) as log_handle:
                fetch_legacy_logs_dir(server, temp_path, log_handle, session)

        make_zip64_archive(zip_path, temp_path)
        return zip_path


def fetch_legacy_logs_dir(server, data_dir, log_handle, session):
    save_path = os.path.join(data_dir, server)
    url = LOG_BASE_URL_LEGACY.format(server=server)

    dirs = [""]

    while dirs:
        dir_path = dirs.pop()
        os.makedirs(os.path.join(save_path, dir_path))

        try:
            contents = session.get(url + dir_path, timeout=(10, None))
        except requests.exceptions.ConnectionError as err:
            log_handle.write(f"Failed to retrieve dir {dir_path}: {err}\n")
            continue

        if contents.status_code != 200:
            log_handle.write(
                f"Failed to retrieve dir {dir_path}: "
                f"{contents.status_code}- {contents.reason}\n"
            )
        files = sorted(
            [
                dir_path + entry["name"]
                for entry in contents.json()
                if entry["type"] == "file"
            ]
        )

        dirs.extend(
            sorted(
                [
                    dir_path + entry["name"] + "/"
                    for entry in contents.json()
                    if entry["type"] == "directory"
                ]
            )
        )

        for file_path in files:
            try:
                downloaded_file = session.get(
                    url + file_path, timeout=(10, None)
                )
            except requests.exceptions.ConnectionError as err:
                log_handle.write(
                    f"Failed to retrieve dir {file_path}: {err}\n"
                )
                continue

            if downloaded_file.status_code == 200:
                log_handle.write(f"Retrieved file {file_path}\n")
                with open(
                    os.path.join(save_path, file_path), "wb"
                ) as file_handle:
                    file_handle.write(downloaded_file.content)
            else:
                log_handle.write(
                    f"Failed to retrieve file {file_path}: "
                    f"{downloaded_file.status_code}- "
                    f"{downloaded_file.reason}\n"
                )

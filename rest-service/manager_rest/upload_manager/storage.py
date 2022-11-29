import os
import shutil

from flask import current_app

from manager_rest.manager_exceptions import UnsupportedFileServerType


class StorageClient:
    """StorageClient is a base class for storage clients"""
    def __init__(self, base_uri: str):
        self.base_uri = base_uri

    def files(self, path: str):
        """List files in the path location"""
        raise NotImplementedError('Should be implemented in subclasses')

    def save(self, src_path: str, dst_path: str):
        """Save files to the target location"""
        raise NotImplementedError('Should be implemented in subclasses')

    def remove(self, path: str):
        """Remove the location"""
        raise NotImplementedError('Should be implemented in subclasses')


class LocalStorageClient(StorageClient):
    """LocalStorageClient implements storage methods for local filesystem"""
    def files(self, path: str):
        # list all files in path and its subdirectories, but not path
        return (
            f[0][len(path)+1:]
            for f in os.walk(path)
            if len(f[0]) > len(path)+1
        )

    def save(self, src_path: str, dst_path: str):
        full_dst_path = os.path.join(self.base_uri, dst_path)
        os.makedirs(os.path.dirname(full_dst_path), exist_ok=True)
        shutil.move(src_path, full_dst_path)
        os.chmod(full_dst_path, 0o755)

    def remove(self, path: str):
        full_path = os.path.join(self.base_uri, path)
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)


def init_storage_client(config):
    match config.file_server_type.lower():
        case 'local':
            client = LocalStorageClient(config.file_server_root)
        case _:
            raise UnsupportedFileServerType(
                f'Unsupported file server type: {config.file_server_type}'
            )
    return client


def list_dir(path: str):
    """List files in path using current storage client"""
    client = storage_client()
    return client.files(path)


def storage_client() -> StorageClient:
    return current_app.extensions.get('storage_client')

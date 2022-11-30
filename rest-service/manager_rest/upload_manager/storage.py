import os
import shutil
from xml.etree import ElementTree

import requests
from flask import current_app

from manager_rest import manager_exceptions


class StorageClient:
    """StorageClient is a base class for storage clients"""
    def __init__(self, base_uri: str):
        self.base_uri = base_uri

    def list(self, path: str):
        """List files in the path location"""
        raise NotImplementedError('Should be implemented in subclasses')

    def put(self, src_path: str, dst_path: str):
        """Save files to the target location"""
        raise NotImplementedError('Should be implemented in subclasses')

    def delete(self, path: str):
        """Remove the location"""
        raise NotImplementedError('Should be implemented in subclasses')


class LocalStorageClient(StorageClient):
    """LocalStorageClient implements storage methods for local filesystem"""
    def list(self, path: str):
        # list all files in path and its subdirectories, but not path
        full_path = os.path.join(self.base_uri, path)
        return (
            f[0][len(full_path)+1:]
            for f in os.walk(full_path)
            if len(f[0]) > len(full_path)+1
        )

    def put(self, src_path: str, dst_path: str):
        full_dst_path = os.path.join(self.base_uri, dst_path)
        os.makedirs(os.path.dirname(full_dst_path), exist_ok=True)
        shutil.move(src_path, full_dst_path)
        os.chmod(full_dst_path, 0o755)

    def delete(self, path: str):
        full_path = os.path.join(self.base_uri, path)
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)


class S3StorageClient(StorageClient):
    """S3StorageClient implements storage methods for S3-compatible storage"""
    XML_NS = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}

    def __init__(self,
                 base_uri: str,
                 bucket_name: str,
                 req_timeout: float):
        super().__init__(base_uri)
        self.bucket_name = bucket_name
        self.req_timeout = req_timeout

    def list(self, path: str):
        params = {}
        if path:
            params.update({'prefix': path})
        response = requests.get(
            self.server_url,
            params=params,
            timeout=self.req_timeout
        )

        xml_et = ElementTree.fromstring(response.content)

        for contents in xml_et.findall('s3:Contents', S3StorageClient.XML_NS):
            key = contents.find('s3:Key', S3StorageClient.XML_NS)
            yield key.text

    def put(self, src_path: str, dst_path: str):
        with open(src_path, 'rb') as data:
            # do we need a multipart upload maybe?
            requests.put(
                f'{self.server_url}/{dst_path}',
                data=data,
                timeout=self.req_timeout,
            )

    def delete(self, path: str):
        requests.delete(
            f'{self.server_url}/{path}',
            timeout=self.req_timeout,
        )

    @property
    def server_url(self):
        return f'{self.base_uri}/{self.bucket_name}'.rstrip('/')


def init_storage_client(config):
    match config.file_server_type.lower():
        case 'local':
            client = LocalStorageClient(config.file_server_root)
        case 's3':
            client = S3StorageClient(
                config.s3_server_url,
                config.s3_resources_bucket,
                config.s3_client_timeout,
            )
        case _:
            raise manager_exceptions.UnsupportedFileServerType(
                f'Unsupported file server type: {config.file_server_type}'
            )
    return client


def list_dir(path: str):
    """List files in path using current storage client"""
    client = storage_client()
    return client.list(path)


def storage_client() -> StorageClient:
    return current_app.extensions.get('storage_client')

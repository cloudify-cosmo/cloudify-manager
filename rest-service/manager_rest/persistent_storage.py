import os
import shutil
import tempfile
from contextlib import contextmanager
from xml.etree import ElementTree

import requests
from flask import current_app

from manager_rest import manager_exceptions
from manager_rest.constants import FILE_SERVER_RESOURCES_FOLDER
from manager_rest.rest.rest_utils import make_streaming_response


class FileStorageHandler:
    """FileStorageHandler is a base class for persistent storage handlers"""
    def __init__(self, base_uri: str):
        self.base_uri = base_uri

    def find(self, path: str, suffixes=None):
        """Return a path to existing file specified by path and suffixes"""
        raise NotImplementedError('Should be implemented in subclasses')

    def get(self, path: str):
        """Return a path to local copy of a file specified by path"""
        raise NotImplementedError('Should be implemented in subclasses')

    def list(self, path: str):
        """List files in the path location"""
        raise NotImplementedError('Should be implemented in subclasses')

    def move(self, src_path: str, dst_path: str):
        """Save files to the target location, removes the local src_path"""
        raise NotImplementedError('Should be implemented in subclasses')

    def delete(self, path: str):
        """Remove the location"""
        raise NotImplementedError('Should be implemented in subclasses')

    def proxy(self, path: str):
        """Return a proxied request to the fileserver"""
        raise NotImplementedError('Should be implemented in subclasses')


class LocalStorageHandler(FileStorageHandler):
    """LocalStorageHandler implements storage methods for local filesystem"""
    def find(self, path: str, suffixes=None):
        """Get a file by its path"""
        full_path = os.path.join(self.base_uri, path)
        if os.path.isfile(full_path):
            return path
        if not suffixes:
            raise manager_exceptions.NotFoundError(
                f'Could not find file: {path}')

        for sfx in suffixes:
            if os.path.isfile(f'{full_path}.{sfx}'):
                return f'{path}.{sfx}'
        raise manager_exceptions.NotFoundError(
            f'Could not find any file: {path}{{{",".join(suffixes)}}}')

    @contextmanager
    def get(self, path: str):
        """Return a path to local copy of a file specified by path"""
        yield os.path.join(self.base_uri, path)

    def list(self, path: str):
        # list all files in path and its subdirectories, but not path
        list_root = os.path.join(self.base_uri, path)
        for dir_path, _, file_names in os.walk(list_root):
            for name in file_names:
                yield os.path.join(
                    path,
                    os.path.relpath(os.path.join(dir_path, name), list_root)
                )

    def move(self, src_path: str, dst_path: str):
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

    def proxy(self, path: str):
        """Use nginx to return the given file to the user.

        :param path: the path of a file to send, under FILE_SERVER_ROOT.
            For example, for path=a/b.txt, the file
            /opt/manager/resources/a/b.txt will be sent to the user
        """
        return make_streaming_response(
            f'{FILE_SERVER_RESOURCES_FOLDER}/{path}')


class S3StorageHandler(FileStorageHandler):
    """S3StorageHandler implements storage methods for S3-compatible storage"""
    XML_NS = {'s3': 'http://s3.amazonaws.com/doc/2006-03-01/'}

    def __init__(self,
                 base_uri: str,
                 bucket_name: str,
                 req_timeout: float):
        super().__init__(base_uri)
        self.bucket_name = bucket_name
        self.req_timeout = req_timeout

    def find(self, path: str, suffixes=None):
        prefix, _, file_name = path.rpartition('/')
        files_in_prefix = list(self.list(prefix))

        if file_name in files_in_prefix:
            return path
        if not suffixes:
            raise manager_exceptions.NotFoundError(
                f'Could not find file: {path}')

        if not path.endswith('.'):
            path += '.'
        for sfx in suffixes:
            if f'{path}{sfx}' in files_in_prefix:
                return f'{path}{sfx}'
        raise manager_exceptions.NotFoundError(
            f'Could not find any file: {path}{{{",".join(suffixes)}}}')

    @contextmanager
    def get(self, path: str):
        response = requests.get(
            os.path.join(self.server_url, path),
            timeout=self.req_timeout
        )
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(response.content)
            temp_file.seek(0)
            yield temp_file.name

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

        for contents in xml_et.findall('s3:Contents', self.XML_NS):
            key = contents.find('s3:Key', self.XML_NS)
            yield key.text

    def move(self, src_path: str, dst_path: str):
        if os.path.isfile(src_path):
            self._put_file(src_path, dst_path)
            return os.remove(src_path)

        src_files = set()
        for dir_path, _, file_names in os.walk(src_path):
            for name in file_names:
                src_files.add(
                    os.path.relpath(os.path.join(dir_path, name), src_path))

        for file_name in src_files:
            self._put_file(
                os.path.join(src_path, file_name),
                os.path.join(dst_path, file_name)
            )
        shutil.rmtree(src_path)

    def _put_file(self, src_path: str, dst_path: str):
        with open(src_path, 'rb') as buffer:
            # Below is a not very aesthetically pleasing workaround for a known
            # bug in requests, which should be solved in requests 3.x
            # https://github.com/psf/requests/issues/4215
            data = buffer
            if _file_is_empty(src_path):
                data = b''

            res = requests.put(
                f'{self.server_url}/{dst_path}',
                data=data,
                timeout=self.req_timeout,
            )

        if not res.ok:
            raise manager_exceptions.FileServerException(
                f'Error uploading {src_path} to {dst_path}: '
                f'HTTP status code {res.status_code}'
            )

    def delete(self, path: str):
        res = requests.delete(
            f'{self.server_url}/{path}',
            timeout=self.req_timeout,
        )
        if not res.ok:
            raise manager_exceptions.FileServerException(
                f'Error deleting: {path}: '
                f'HTTP status code {res.status_code}'
            )

    def proxy(self, path: str):
        # the /resources-s3/ prefix in here, must match the location
        # of the s3 fileserver in nginx
        return make_streaming_response(f'/resources-s3/{path}')

    @property
    def server_url(self):
        return f'{self.base_uri}/{self.bucket_name}'.rstrip('/')


def _file_is_empty(file_name):
    return os.stat(file_name).st_size == 0


def init_storage_handler(config):
    """Initialize storage handler object based on provided configuration"""
    match config.file_server_type.lower():
        case 'local':
            return LocalStorageHandler(
                config.file_server_root,
            )
        case 's3':
            return S3StorageHandler(
                config.s3_server_url,
                config.s3_resources_bucket,
                config.s3_client_timeout,
            )
        case _:
            raise manager_exceptions.UnsupportedFileServerType(
                f'Unsupported file server type: {config.file_server_type}'
            )


def get_storage_handler() -> FileStorageHandler:
    """Get the storage_handler object from Cloudify Flask app"""
    return current_app.extensions['storage_handler']

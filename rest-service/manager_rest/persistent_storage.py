import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import dataclass
from xml.etree import ElementTree

import boto3
from flask import current_app

from manager_rest import manager_exceptions
from manager_rest.rest.rest_utils import make_streaming_response


LAST_MODIFIED_FMT = '%Y-%m-%dT%H:%M:%S.%f%z'


@dataclass(slots=True)
class FileInfo:
    """FileInfo is a class used to represent information about a file"""
    filepath: str
    mtime: str

    def __init__(self, filepath: str, mtime: str):
        self.filepath = filepath
        self.mtime = mtime

    @classmethod
    def from_local_file(cls, descriptive_filepath: str, filepath: str):
        file_mtime = datetime.fromtimestamp(os.stat(filepath).st_mtime,
                                            tz=timezone.utc)
        return FileInfo(
            filepath=descriptive_filepath,
            mtime=file_mtime.isoformat(),
        )

    @classmethod
    def from_s3_file(cls,
                     filepath: ElementTree.Element,
                     last_modified: ElementTree.Element):
        return FileInfo(
            filepath=filepath,
            mtime=last_modified.isoformat(),
        )

    def serialize(self, rel_path=None):
        if rel_path:
            file_path = os.path.relpath(self.filepath, rel_path)
        else:
            file_path = self.filepath

        return {file_path: self.mtime}


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

    def list(self, path: str) -> [FileInfo]:
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

    def list(self, path: str) -> [FileInfo]:
        # list all files in path and its subdirectories, but not path
        list_root = os.path.join(self.base_uri, path)
        if not os.path.exists(list_root):
            raise manager_exceptions.NotFoundError()
        for dir_path, _, file_names in os.walk(list_root):
            for name in file_names:
                file_path = os.path.join(
                    path,
                    os.path.relpath(os.path.join(dir_path, name), list_root)
                )
                file_abs_path = os.path.join(self.base_uri, file_path)
                yield FileInfo.from_local_file(file_path, file_abs_path)

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
        # the /resources-local/ prefix in here, must match the location
        # of the local fileserver in nginx
        return make_streaming_response(f'/resources-local/{path}')


class S3StorageHandler(FileStorageHandler):
    """S3StorageHandler implements storage methods for S3-compatible storage"""
    def __init__(self,
                 base_uri: str | None,
                 bucket_name: str,
                 req_timeout: float):
        super().__init__(base_uri)
        self.s3_client = boto3.client('s3', endpoint_url=base_uri)
        self.s3 = boto3.resource('s3', endpoint_url=base_uri)
        self.bucket = self.s3.Bucket(bucket_name)
        self.bucket_name = bucket_name

    def find(self, path: str, suffixes=None):
        prefix, _, file_name = path.rpartition('/')
        files_in_prefix = [fi.filepath for fi in self.list(prefix)]

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
        with tempfile.NamedTemporaryFile() as temp_file:
            self.bucket.download_fileobj(
                Key=path,
                Fileobj=temp_file,
            )
            temp_file.seek(0)
            yield temp_file.name

    def list(self, path: str) -> [FileInfo]:
        params = {}
        if path:
            params.update({'prefix': path})
        for obj in self.bucket.objects.filter(
            Prefix=path,
        ):
            yield FileInfo.from_s3_file(
                obj.key,
                obj.last_modified,
            )

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

            self.bucket.put_object(
                Key=dst_path,
                Body=data,
            )

    def delete(self, path: str):
        self.bucket.objects.filter(Prefix=path).delete()

    def proxy(self, path: str):
        # to proxy to a s3 resource, generate a pre-signed url, and pass that
        # in a header to nginx; nginx will then use proxy_pass to proxy
        # that resource back to the user
        presigned_url = self.s3_client.generate_presigned_url(
            'get_object', Params={
                'Bucket': self.bucket_name,
                'Key': path
            },
            ExpiresIn=60,
        )
        resp = make_streaming_response(f'/resources-s3/{path}')
        resp.headers['X-S3-URI'] = presigned_url
        return resp


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
                config.s3_server_url or None,
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

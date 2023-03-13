import requests
import requests.sessions
from requests_toolbelt import MultipartEncoder

from cloudify.utils import get_admin_api_token


class UIClientError(Exception):
    def __init__(self, operation, status_code, reason):
        self.operation = operation
        self.status_code = status_code
        self.reason = reason

    def __str__(self):
        return f'{self.operation} failed: {self.reason} '\
               f'(HTTP {self.status_code})'


class ComposerBaseSnapshotClient:
    """A base client for Cloudify Composer snapshots."""
    _base_url: str

    def __init__(self, base_url: str):
        self._base_url = base_url
        _, _, self._entity_name = base_url.rpartition('/')

    def _url(self, suffix: str = ''):
        url = self._base_url
        if suffix:
            url = f"{url.rstrip('/')}/{suffix}"
        return url

    @staticmethod
    def _request_headers(**kwargs):
        headers = {'authentication_token': get_admin_api_token()}
        headers.update(kwargs)
        return headers

    def get_snapshot(self, expected_status_code=200):
        """Retrieve a snapshot of Composer entities."""
        with requests.session() as session:
            resp = session.get(self._url(),
                               headers=self._request_headers(),
                               stream=True)
        if resp.status_code != expected_status_code:
            raise UIClientError(
                f'getting composer snapshot of {self._entity_name}',
                resp.status_code,
                resp.reason,
            )
        return resp.content


class ComposerBlueprintsSnapshotClient(ComposerBaseSnapshotClient):
    """A client for Cloudify Composer blueprints' snapshots and metadata."""
    def get_metadata(self, expected_status_code=200):
        """Retrieve Composer blueprints' metadata."""
        with requests.session() as session:
            resp = session.get(self._url('metadata'),
                               headers=self._request_headers(),
                               stream=True)
        if resp.status_code != expected_status_code:
            raise UIClientError(
                f'getting composer metadata of {self._entity_name}',
                resp.status_code,
                resp.reason,
            )
        return resp.content


class ComposerClient:
    """A client for Cloudify Composer"""
    _base_url: str

    def __init__(self, base_url):
        self._base_url = base_url
        self.blueprints = ComposerBlueprintsSnapshotClient(
            f'{self._base_url}/snapshots/blueprints')
        self.configuration = ComposerBaseSnapshotClient(
            f'{self._base_url}/snapshots/configuration')
        self.favorites = ComposerBaseSnapshotClient(
            f'{self._base_url}/snapshots/favorites')

    def put_snapshot(self, dump_type, file_path, expected_status=201):
        """Post (restore) snapshot of dump_type entities."""
        request_headers = {
            'authentication-token': get_admin_api_token(),
            'content-type': 'application/json; charset=utf-8',
        }
        with open(file_path, 'rb') as data:
            with requests.session() as session:
                r = session.post(f'{self._base_url}/snapshots/{dump_type}',
                                 headers=request_headers,
                                 data=data)
        if r.status_code != expected_status:
            raise UIClientError(
                f'recreation of composer snapshot of {dump_type}',
                r.status_code,
                r.reason,
            )

    def put_blueprints_snapshot(self,
                                metadata_file_path,
                                snapshot_file_path,
                                expected_status=201):
        """Post (restore) blueprint snapshot."""
        request_headers = {'authentication-token': get_admin_api_token()}
        mp_encoder = MultipartEncoder(
            fields={
                'metadata': (
                    'blueprints.json',
                    open(metadata_file_path, 'rb'),
                    'application/json',
                ),
                'snapshot': (
                    'blueprints.zip',
                    open(snapshot_file_path, 'rb'),
                    'application/zip',
                ),
            }
        )
        with requests.session() as session:
            r = session.post(f'{self._base_url}/snapshots/blueprints',
                             headers=request_headers,
                             data=mp_encoder)
        if r.status_code != expected_status:
            raise UIClientError(
                'recreation of composer snapshot of blueprints',
                r.status_code,
                r.reason,
            )

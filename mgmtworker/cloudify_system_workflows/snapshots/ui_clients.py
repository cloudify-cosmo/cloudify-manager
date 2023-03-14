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
    def _request_headers(extra_headers=None):
        headers = {'authentication-token': get_admin_api_token()}
        if extra_headers:
            headers.update(headers)
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

    def restore_snapshot(self, snapshot_file_name, expected_status_code=201):
        request_headers = self._request_headers({
            'content-type': 'application/json; charset=utf-8',
        })
        with open(snapshot_file_name, 'rb') as data:
            with requests.session() as session:
                resp = session.post(self._url(),
                                    headers=request_headers,
                                    data=data)
        if resp.status_code != expected_status_code:
            raise UIClientError(
                f'restoring composer snapshot of {self._entity_name}',
                resp.status_code,
                resp.reason,
            )


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

    def restore_snapshot_and_metadata(self,
                                      snapshot_file_name,
                                      metadata_file_name,
                                      expected_status_code=201):
        mp_encoder = MultipartEncoder(
            fields={
                'metadata': (
                    'blueprints.json',
                    open(metadata_file_name, 'rb'),
                    'application/json',
                ),
                'snapshot': (
                    'blueprints.zip',
                    open(snapshot_file_name, 'rb'),
                    'application/zip',
                ),
            }
        )
        with requests.session() as session:
            resp = session.post(self._url(),
                                headers=self._request_headers(),
                                data=mp_encoder)
        if resp.status_code != expected_status_code:
            raise UIClientError(
                'restoring composer snapshot of blueprints',
                resp.status_code,
                resp.reason,
            )


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

import requests
import requests.sessions

from cloudify.utils import get_admin_api_token


class UIClientError(Exception):
    """An exception raised by (any of) UI clients."""
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
            headers.update(extra_headers)
        return headers

    def get_snapshot(self, expected_status_code=requests.codes.ok):
        """Retrieve a snapshot of Composer entities."""
        with requests.session() as session:
            resp = session.get(self._url(),
                               headers=self._request_headers(),
                               stream=True)
        handle_response(f'getting composer snapshot of {self._entity_name}',
                        expected_status_code, resp)
        return resp.content

    def restore_snapshot(self, snapshot_file_name,
                         expected_status_code=requests.codes.created):
        """Restore a snapshot of Composer entities."""
        request_headers = self._request_headers({
            'content-type': 'application/json; charset=utf-8',
        })
        with open(snapshot_file_name, 'rb') as data:
            with requests.session() as session:
                resp = session.post(self._url(),
                                    headers=request_headers,
                                    data=data)
        handle_response(f'restoring composer snapshot of {self._entity_name}',
                        expected_status_code, resp)


class ComposerBlueprintsSnapshotClient(ComposerBaseSnapshotClient):
    """A client for Cloudify Composer blueprints' snapshots and metadata."""
    def get_metadata(self, expected_status_code=requests.codes.ok):
        """Retrieve Composer blueprints' metadata."""
        with requests.session() as session:
            resp = session.get(self._url('metadata'),
                               headers=self._request_headers(),
                               stream=True)
        handle_response(f'getting composer metadata of {self._entity_name}',
                        expected_status_code, resp)
        return resp.content

    def restore_snapshot_and_metadata(
            self, snapshot_file_name, metadata_file_name,
            expected_status_code=requests.codes.created):
        """Restore blueprint's snapshot and metadata"""
        request_files = {
            'metadata': (None, open(metadata_file_name, 'rb')),
            'snapshot': (None, open(snapshot_file_name, 'rb')),
        }
        with requests.session() as session:
            resp = session.post(self._url(),
                                headers=self._request_headers(),
                                files=request_files)
        handle_response('restoring composer snapshot of blueprints',
                        expected_status_code, resp)


def handle_response(operation: str, expected_status_code: int,
                    response: requests.Response):
    """Validate response status_code against expected status_code"""
    if response.status_code != expected_status_code:
        try:
            description = response.json().get('description')
        except requests.exceptions.JSONDecodeError:
            description = response.reason
        raise UIClientError(operation, response.status_code, description)


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

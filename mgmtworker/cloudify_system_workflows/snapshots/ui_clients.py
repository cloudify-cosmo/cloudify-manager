import json

import requests
import requests.sessions
from requests_toolbelt import MultipartEncoder

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


def handle_response(operation: str, expected_status_code: int,
                    response: requests.Response):
    """Validate response status_code against expected status_code"""
    if response.status_code != expected_status_code:
        try:
            description = response.json().get('description')
        except requests.exceptions.JSONDecodeError:
            description = response.reason
        if not description:
            description = response.reason
        raise UIClientError(operation, response.status_code, description)


class UIBaseSnapshotClient:
    """A base client for Cloudify UI snapshots."""
    _base_url: str
    _ui_service_name: str

    def __init__(self, base_url: str, ui_service_name: str):
        self._base_url = base_url
        self._ui_service_name = ui_service_name
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
            headers.update({
                k: v for k, v in extra_headers.items() if v is not None
            })
        return headers

    def get_snapshot(self, tenant=None,
                     expected_status_code=requests.codes.ok):
        """Retrieve a snapshot of UI entities."""
        headers = self._request_headers({'tenant': tenant})
        with requests.session() as session:
            resp = session.get(self._url(), headers=headers, stream=True)
        handle_response(f'getting {self._ui_service_name} snapshot '
                        f'of {self._entity_name}',
                        expected_status_code, resp)
        return resp.content

    def restore_snapshot(self, snapshot_file_name, tenant=None,
                         expected_status_code=requests.codes.created):
        """Restore a snapshot of UI entities."""
        headers = self._request_headers({
            'content-type': 'application/json; charset=utf-8',
            'tenant': tenant,
        })
        with open(snapshot_file_name, 'rb') as snapshot_handle:
            data = json.load(snapshot_handle)['items']
        with requests.session() as session:
            resp = session.post(self._url(), headers=headers,
                                data=json.dumps(data).encode('utf-8'))
        handle_response(f'restoring {self._ui_service_name} snapshot '
                        f'of {self._entity_name}',
                        expected_status_code, resp)


class ComposerBaseSnapshotClient(UIBaseSnapshotClient):
    """A base client for Cloudify Composer snapshots."""
    def __init__(self, base_url: str):
        super().__init__(base_url, 'composer')


class ComposerBlueprintsSnapshotClient(ComposerBaseSnapshotClient):
    """A client for Cloudify Composer blueprints' snapshots and metadata."""
    def get_metadata(self,  tenant=None,
                     expected_status_code=requests.codes.ok):
        """Retrieve Composer blueprints' metadata."""
        headers = self._request_headers({'tenant': tenant})
        with requests.session() as session:
            resp = session.get(self._url('metadata'),
                               headers=headers,
                               stream=True)
        handle_response(f'getting composer metadata of {self._entity_name}',
                        expected_status_code, resp)
        return resp.content

    def restore_snapshot_and_metadata(
            self, snapshot_file_name, metadata_file_name,
            tenant=None, expected_status_code=requests.codes.created):
        """Restore blueprint's snapshot and metadata"""
        with open(metadata_file_name, 'rb') as metadata_handle:
            metadata = json.load(metadata_handle)['items']
        data = MultipartEncoder({
            'metadata': ('blueprints.json',
                         json.dumps(metadata).encode('utf-8'),
                         'application/json'),
            'snapshot': ('blueprints.zip',
                         open(snapshot_file_name, 'rb'),
                         'application/zip'),
        })
        headers = self._request_headers({'content-type': data.content_type,
                                         'tenant': tenant})
        with requests.session() as session:
            resp = session.post(self._url(), headers=headers, data=data)
        handle_response(f'restoring composer snapshot of {self._entity_name}',
                        expected_status_code, resp)


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


class StageBaseSnapshotClient(UIBaseSnapshotClient):
    """A base client for Cloudify Stage snapshots."""
    def __init__(self, base_url: str):
        super().__init__(base_url, 'stage')


class StageWidgetsSnapshotClient(StageBaseSnapshotClient):
    def restore_snapshot(self, snapshot_file_name, tenant=None,
                         expected_status_code=requests.codes.created):
        """Restore a snapshot of Stage widgets."""
        headers = self._request_headers({'tenant': tenant})
        request_files = {
            'snapshot': ('snapshot', open(snapshot_file_name, 'rb')),
        }
        with requests.session() as session:
            resp = session.post(self._url(), headers=headers,
                                files=request_files)
        handle_response(f'restoring stage snapshot of {self._entity_name}',
                        expected_status_code, resp)


class StageClient:
    """A client for Cloudify Composer"""
    _base_url: str

    def __init__(self, base_url):
        self._base_url = base_url
        self.blueprint_layouts = StageBaseSnapshotClient(
            f'{self._base_url}/snapshots/blueprint-layouts')
        self.configuration = StageBaseSnapshotClient(
            f'{self._base_url}/snapshots/configuration')
        self.page_groups = StageBaseSnapshotClient(
            f'{self._base_url}/snapshots/page-groups')
        self.pages = StageBaseSnapshotClient(
            f'{self._base_url}/snapshots/pages')
        self.templates = StageBaseSnapshotClient(
            f'{self._base_url}/snapshots/templates')
        self.ua = StageBaseSnapshotClient(
            f'{self._base_url}/snapshots/ua')
        self.widgets = StageWidgetsSnapshotClient(
            f'{self._base_url}/snapshots/widgets')

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


class ComposerClient:
    """An HTTP client for Cloudify Composer"""
    _base_url: str

    def __init__(self, base_url):
        self._base_url = base_url

    def get_snapshots(self, dump_type, suffix=None):
        """Retrieve snapshot of dump_type entities."""
        if suffix:
            dump_type += f'/{suffix}'
        request_url = f'{self._base_url}/snapshots/{dump_type}'
        request_headers = {'authentication-token': get_admin_api_token()}
        with requests.session() as session:
            r = session.get(request_url,
                            headers=request_headers,
                            stream=True)
            if r.status_code != 200:
                raise UIClientError(
                    f'getting composer snapshot of {dump_type}',
                    r.status_code,
                    r.reason,
                )
            return r.content

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

from integration_tests.framework import docl
from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource
from cloudify_rest_client.exceptions import (
    MissingCloudifyLicense,
    ExpiredCloudifyLicense,
    CloudifyClientError
)


class TestLicense(AgentlessTestCase):

    def setUp(self):
        super(TestLicense, self).setUp()
        docl.remove_license()

    def test_error_when_no_license_on_manager(self):
        """
        Most REST endpoints are blocked when there is no Cloudify license
        on the Manager, the `blueprints` endpoint was chosen randomly
        for this test.
        """
        self.assertRaises(MissingCloudifyLicense,
                          self.client.blueprints.list)

    def test_no_error_when_using_allowed_endpoints(self):
        """
        The following endpoints are allowed even when there is no Cloudify
        license on the Manager: tenants, status, license, snapshots, tokens,
        maintenance.
        """
        self.client.tokens.get()
        self.client.tenants.list()
        self.client.license.list()
        self.client.snapshots.list()
        self.client.manager.get_status()
        self.client.maintenance_mode.status()

    def _upload_license(self, license):
        license_path = get_resource('licenses/{0}'.format(license))
        self.client.license.upload(license_path)

    def _verify_license(self, expired, trial):
        license = self.client.license.list().items[0]
        self.assertEqual(license['expired'], expired)
        self.assertEqual(license['trial'], trial)

    def test_upload_valid_paying_license(self):
        self._upload_license('test_valid_paying_license.yaml')
        self._verify_license(expired=False, trial=False)
        self.client.blueprints.list()

    def test_upload_valid_trial_license(self):
        self._upload_license('test_valid_trial_license.yaml')
        self._verify_license(expired=False, trial=True)
        self.client.blueprints.list()

    def test_error_when_uploading_tampered_trial_license(self):
        try:
            self._upload_license('test_tampered_trial_license.yaml')
        except CloudifyClientError as e:
            self.assertIn('This license could not be verified', e.message)

    def test_error_when_uploading_tampered_paying_license(self):
        try:
            self._upload_license('test_tampered_paying_license.yaml')
        except CloudifyClientError as e:
            self.assertIn('This license could not be verified', e.message)

    def test_error_when_using_expired_trial_license(self):
        self._upload_license('test_expired_trial_license.yaml')
        self._verify_license(expired=True, trial=True)
        try:
            self.client.blueprints.list()
        except ExpiredCloudifyLicense as e:
            self.assertIn('This Manager`s Cloudify license has expired',
                          e.message)

    def test_using_expired_paying_license(self):
        self._upload_license('test_expired_paying_license.yaml')
        self._verify_license(expired=True, trial=False)
        self.client.blueprints.list()

    def test_upload_two_licenses(self):
        """
        There can only be one Cloudify license on the Manager, so each time
        a user uploads a license it runs over the old license.
        """
        self._upload_license('test_expired_paying_license.yaml')
        self._verify_license(expired=True, trial=False)
        self._upload_license('test_valid_trial_license.yaml')
        self._verify_license(expired=False, trial=True)

    def test_upload_tampered_license_after_valid_license(self):
        """
        - Upload a valid Cloudify license
        - Try (and fail) to upload a tampered license
        - Make sure REST is not blocked
        """
        self._upload_license('test_valid_paying_license.yaml')
        self._verify_license(expired=False, trial=False)
        try:
            self._upload_license('test_tampered_paying_license.yaml')
        except CloudifyClientError as e:
            self.assertIn('This license could not be verified', e.message)
        self.client.blueprints.list()

########
# Copyright (c) 2019 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from datetime import datetime, timedelta

from integration_tests import AgentlessTestCase
from integration_tests.framework import postgresql
from integration_tests.tests.utils import get_resource
from cloudify_rest_client.exceptions import (
    MissingCloudifyLicense,
    ExpiredCloudifyLicense,
    CloudifyClientError
)


class TestLicense(AgentlessTestCase):

    def setUp(self):
        super(TestLicense, self).setUp()
        postgresql.run_query("DELETE FROM licenses")

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

    def test_valid_for_30_days_license(self):
        """
        Instead of a specific expiration date this license is valid for 30 days
        from Manager installation date.
        """
        self._upload_license('test_30_days_license.yaml')
        license = self.client.license.list().items[0]
        self._verify_license(expired=False, trial=True)
        expected_date = datetime.utcnow() + timedelta(days=30)
        expiration_date = datetime.strptime(license['expiration_date'],
                                            '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertLessEqual(expiration_date, expected_date)
        self.client.blueprints.list()

    def test_license_valid_for_all_version(self):
        """
        Cloudify licenses with empty `version` value are valid for all
        Cloudify versions.
        """
        self._upload_license('test_no_version_license.yaml')
        license = self.client.license.list().items[0]
        self._verify_license(expired=False, trial=True)
        self.assertIsNone(license['cloudify_version'])
        self.client.blueprints.list()

    def test_error_when_uploading_license_with_old_version(self):
        """
        Try (and fail) to upload a Cloudify license that is valid for
        Cloudify 4.5.5
        """
        try:
            self._upload_license('test_version_4_5_5_license.yaml')
        except CloudifyClientError as e:
            self.assertIn('This license could not be verified', e.message)

    def test_license_with_no_expiration_date(self):
        """
        Cloudify licenses with empty `expiration_date` value are valid
        for good.
        """
        self._upload_license('test_no_expiration_date_license.yaml')
        license = self.client.license.list().items[0]
        self._verify_license(expired=False, trial=True)
        self.assertIsNone(license['expiration_date'])
        self.client.blueprints.list()

    def _upload_license(self, license):
        license_path = get_resource('licenses/{0}'.format(license))
        self.client.license.upload(license_path)

    def _verify_license(self, expired, trial):
        license = self.client.license.list().items[0]
        self.assertEqual(license['expired'], expired)
        self.assertEqual(license['trial'], trial)

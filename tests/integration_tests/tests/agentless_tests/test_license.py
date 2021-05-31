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

import pytest
import tempfile
from datetime import datetime, timedelta

import requests

from integration_tests import AgentlessTestCase
from integration_tests.tests.utils import get_resource
from integration_tests.framework.constants import INSERT_MOCK_LICENSE_QUERY
from cloudify_rest_client.exceptions import (
    MissingCloudifyLicense,
    ExpiredCloudifyLicense,
    CloudifyClientError
)
from integration_tests.tests.utils import run_postgresql_command

pytestmark = pytest.mark.group_premium
LICENSE_ENGINE_URL = 'https://us-central1-omer-tenant.cloudfunctions' \
                     '.net/LicenseEngineHubSpot'


class TestLicense(AgentlessTestCase):

    def setUp(self):
        super(TestLicense, self).setUp()
        run_postgresql_command(self.env.container_id, "DELETE FROM licenses")

    def tearDown(self):
        super(TestLicense, self).setUp()
        run_postgresql_command(self.env.container_id, "DELETE FROM licenses")
        run_postgresql_command(self.env.container_id,
                               INSERT_MOCK_LICENSE_QUERY)

    def test_error_when_no_license_on_manager(self):
        """
        Most REST endpoints are blocked when there is no Cloudify license
        on the Manager, the `blueprints` endpoint was chosen randomly
        for this test.
        """
        self.assertRaises(MissingCloudifyLicense,
                          self.client.blueprints.list)

    def test_error_when_no_license_substring_endpoint(self):
        """
        Restricted endpoint that partly contains allowed endpoint should not
        be allowed. For example: `snapshot-status` is not allowed even
        though `status` is allowed
        """
        self.assertRaises(MissingCloudifyLicense,
                          self.client.snapshots.get_status)

    def test_no_error_when_using_allowed_endpoints(self):
        """
        The following endpoints are allowed even when there is no Cloudify
        license on the Manager: tenants, status, license, snapshots, tokens,
        maintenance.
        """
        self.client.tokens.get()
        self.client.tenants.list()
        self.client.license.list()
        self.client.manager.get_status()

    def test_no_error_when_using_get_user(self):
        self.client.users.get('admin', _get_data=True)

    def test_error_when_using_allowed_endpoint_and_forbidden_method(self):
        self.assertRaises(MissingCloudifyLicense,
                          self.client.users.create,
                          username='user', password='password', role='default')

    def test_upload_valid_paying_license(self):
        self._upload_license('test_valid_paying_license.yaml')
        self._verify_license(expired=False, trial=False)
        self.client.blueprints.list()

    def test_upload_valid_trial_license(self):
        self._upload_license('test_valid_trial_license.yaml')
        self._verify_license(expired=False, trial=True)
        self.client.blueprints.list()

    def test_error_when_uploading_tampered_trial_license(self):
        with self.assertRaisesRegex(CloudifyClientError,
                                    'could not be verified'):
            self._upload_license('test_tampered_trial_license.yaml')

    def test_error_when_uploading_tampered_paying_license(self):
        with self.assertRaisesRegex(CloudifyClientError,
                                    'could not be verified'):
            self._upload_license('test_tampered_paying_license.yaml')

    def test_error_when_using_expired_trial_license(self):
        self._upload_license('test_expired_trial_license.yaml')
        self._verify_license(expired=True, trial=True)
        with self.assertRaisesRegex(ExpiredCloudifyLicense, 'expired'):
            self.client.blueprints.list()

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
        with self.assertRaisesRegex(CloudifyClientError,
                                    'could not be verified'):
            self._upload_license('test_tampered_paying_license.yaml')
        self.client.blueprints.list()

    def test_valid_for_60_days_license(self):
        """
        Instead of a specific expiration date this license is valid for 60 days
        from Manager installation date.
        """
        self._upload_license('test_60_days_license.yaml')
        license = self.client.license.list().items[0]
        self._verify_license(expired=False, trial=True)
        expected_date = datetime.utcnow() + timedelta(days=60)
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
        with self.assertRaisesRegex(CloudifyClientError, 'versions'):
            self._upload_license('test_version_4_5_5_license.yaml')

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

    def test_gcp_license_engine(self):
        """
        Send request to the GCP license engine and make sure the license
        received is indeed valid.
        """
        json_data = {'vid': 5464472,
                     'properties':
                         {'email': {'value': 'awesome@gre.at'}}}

        response = requests.post(url=LICENSE_ENGINE_URL, json=json_data)

        with tempfile.NamedTemporaryFile(mode='w') as license_file:
            license_file.write(response.text)
            license_file.flush()
            self.client.license.upload(license_file.name)

        self._verify_license(expired=False, trial=True)
        license = self.client.license.list().items[0]
        customer_id = self._get_customer_id(json_data)
        self.assertEqual(license['customer_id'], customer_id)
        self.client.blueprints.list()

    @staticmethod
    def _get_customer_id(json_data):
        vid = str(json_data['vid'])
        email = json_data['properties']['email']['value']
        domain = email.split('@')[1] + '-'
        return 'TRL-' + domain + vid

    def _upload_license(self, license):
        license_path = get_resource('licenses/{0}'.format(license))
        self.client.license.upload(license_path)

    def _verify_license(self, expired, trial):
        license = self.client.license.list().items[0]
        self.assertEqual(license['expired'], expired)
        self.assertEqual(license['trial'], trial)

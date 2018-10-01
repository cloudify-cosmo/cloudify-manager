#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.
from flask import current_app
from opentracing import UnsupportedFormatException

from manager_rest.test import base_test
from manager_rest.test.attribute import attr


@attr(client_min_version=1, client_max_version=base_test.LATEST_API_VERSION)
class AppTestCase(base_test.BaseServerTestCase):
    """Test the basic HTTP interface, app-wide error handling
    """

    def test_get_root_404(self):
        """GET / returns a 404.

        Check that the app can handle requests that couldn't be routed,
        doesn't break with a 500.
        """
        resp = self.app.get('/')
        self.assertEqual(404, resp.status_code)

    def test_does_not_init_tracer(self):
        # Dummy call to invoke the tracer initialization if enabled.
        self.app.get('/')
        self.jaeger_mock_config.assert_not_called()


@attr(client_min_version=base_test.LATEST_API_VERSION,
      client_max_version=base_test.LATEST_API_VERSION)
class AppWithTracingNoIPTestCase(base_test.TracerTestCase):
    """Test the basic setup of the tracer and dispatch wrapping for the
    tracing when tracing is enabled but no endpoint IP is set.
    """
    setup_config_enable_tracing = True
    setup_config_tracing_endpoint_ip = None

    def test_does_not_init_tracer_no_tracer_ip(self):
        self.jaeger_mock_config.assert_not_called()


@attr(client_min_version=base_test.LATEST_API_VERSION,
      client_max_version=base_test.LATEST_API_VERSION)
class AppWithTracingTestCase(base_test.TracerTestCase):
    """Test the basic setup of the tracer and dispatch wrapping for the
    tracing when tracing is enabled and an endpoint IP is set.
    """
    setup_config_enable_tracing = True
    setup_config_tracing_endpoint_ip = 'some_ip'

    def test_does_init_tracer(self):
        self.jaeger_mock_config.assert_called_with(
            config={
                'sampler': {'type': 'const', 'param': 1},
                'local_agent': {
                    'reporting_host': 'some_ip'},
                'logging': True
            },
            service_name='cloudify-manager'
        )
        self.jaeger_mock_config.initialize_tracer.assert_called()

    def test_adds_error_to_tags(self):
        e = UnsupportedFormatException()
        start_span_kwargs = {'tags': {"Extract failed": str(e)},
                             'operation_name': 'None (GET)'}

        def _raises(*_, **__):
            raise e

        tracer = current_app.tracer
        tracer.extract.side_effect = _raises
        self.app.get('/')
        tracer.start_span.assert_called_with(**start_span_kwargs)

########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
import elasticsearch

from testenv import TestCase
from testenv import utils
from testenv.utils import get_resource as resource
from testenv.utils import deploy_application as deploy

ELASTICSEARCH_PORT = 9200
TIMESTAMP_PATTERN = '\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z'
DEFAULT_EXECUTE_TIMEOUT = 1800


class ElasticsearchTimestampFormatTest(TestCase):
    """
    CFY-54
    this test checks Elasticsearch Timestamp Format.
    it creates events by uploading a blueprint and creating deployment.
    after creating events the test connects to Elasticsearch and compares
    Timestamp Format of the events to a regular expression.
    """

    def test_events_timestamp_format(self):
        dsl_path = resource('dsl/empty_blueprint.yaml')
        deployment, _ = deploy(dsl_path)

        #  connect to Elastic search
        es = elasticsearch.Elasticsearch(hosts=[{
            'host': utils.get_manager_ip(),
            'port': 9200}]
        )
        index = "cloudify_events" if es.indices.exists(
            index=["cloudify_events"]) else "logstash-*"

        def read_events():
            res = es.search(index=index, body={"query": {"match":
                            {"deployment_id": deployment.id}}})
            #  check if events were created
            self.assertNotEqual(0, res['hits']['total'],
                                'There are no events in for '
                                'deployment ' + deployment.id)
            return res

        result = self.do_assertions(read_events, timeout=120)

        #  loop over all the events and compare timestamp to regular expression
        for hit in result['hits']['hits']:
            if not (re.match(TIMESTAMP_PATTERN, hit["_source"]['timestamp'])):
                self.fail('Got {0}. Does not match format '
                          'YYYY-MM-DDTHH:MM:SS.***Z'
                          .format(hit["_source"]['timestamp']))

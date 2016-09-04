# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from nose.plugins.attrib import attr
from mock import patch

from manager_rest.test import base_test
from manager_rest.resources_v2 import Events
from manager_rest.storage.manager_elasticsearch import ManagerElasticsearch


@attr(client_min_version=2, client_max_version=base_test.LATEST_API_VERSION)
class EventsTest(base_test.BaseServerTestCase):

    def test_obsolete_post_request(self):
        response = self.post('/events', {})
        self.assertEqual(405, response.status_code)

    def test_build_query_no_args(self):
        # make sure nothing crashes...
        Events._build_query()

    def test_list_events(self):
        ManagerElasticsearch.search_events = self._mock_es_search
        response = self.client.events.list()
        total = self._mock_es_search()['hits']['total']
        hits = self._mock_es_search()['hits']['hits']
        self.assertEquals(total, response.metadata.pagination.total)
        self.assertEquals(len(hits), len(response.items))

    @attr(client_min_version=2.1,
          client_max_version=base_test.LATEST_API_VERSION)
    def test_delete_events(self):
        def delete_events(bpm_self, events_list):
            for index, event in enumerate(events_list):
                self.assertEqual(event['doc_type'], 'cloudify_log')
                self.assertEqual(event['id'], 'id_{0}'.format(index + 1))
                self.assertEqual(event['index'], 'logstash-1')

        ManagerElasticsearch.search_events = self._mock_es_search_delete
        patch_path = ('manager_rest.blueprints_manager.BlueprintsManager.'
                      'delete_events')
        with patch(patch_path, delete_events):
            response = self.client.events.delete('dep_id', include_logs=True)
            self.assertEqual(response.items, [5])

    def test_build_query(self):
        self.maxDiff = None
        filters, pagination, sort, range_filters = self._get_build_query_args()
        query = Events._build_query(filters=filters,
                                    sort=sort,
                                    pagination=pagination,
                                    range_filters=range_filters)
        expected_query = self._get_expected_query()
        # match the order of conditions list in both queries
        # to overcome order differences in comparison
        self._sort_query_conditions_list(expected_query)
        self._sort_query_conditions_list(query)

        self.assertDictEqual(expected_query, query)

    def _get_build_query_args(self):

        filters = {
            'blueprint_id': ['some_blueprint'],
            'deployment_id': ['some_deployment'],
            'type': ['cloudify_event', 'cloudify_logs']
        }
        pagination = {
            'size': 5,
            'offset': 3
        }
        sort = {
            '@timestamp': 'desc'
        }
        range_filters = {
            '@timestamp': {
                'from': '2015-01-01T15:00:0',
                'to': '2016-12-31T01:00:0'
            }
        }
        return filters, pagination, sort, range_filters

    def _mock_es_search(self, *args, **kwargs):
        result = {
            'hits': {
                'total': 10,
                'hits': [{'_source': {k: k}} for k in range(1, 6)]
            }
        }
        return result

    def _mock_es_search_delete(self, *args, **kwargs):
        expected_must_list = [
            {
                'terms': {
                    'type': [
                        u'cloudify_event',
                        u'cloudify_log'
                    ]
                }
            },
            {
                'query': {
                    'match': {
                        'context.deployment_id': {
                            'operator': 'and',
                            'query': u'dep_id'
                        }
                    }
                }
            }
        ]
        expected_body = {
            'query': {
                'filtered': {
                    'filter': {
                        'bool': {
                            'must': expected_must_list
                        }
                    }
                }
            },
            'size': 10000
        }

        self.assertIn('body', kwargs)
        try:
            actual_must_list = \
                kwargs['body']['query']['filtered']['filter']['bool']['must']
        except KeyError as e:
            self.fail('unexpected body structure: {0}'.format(str(e)))
        actual_must_list.sort()
        expected_must_list.sort()
        self.assertDictEqual(kwargs['body'], expected_body)

        return {
            'hits': {
                'hits': [
                    {
                        '_id': 'id_1',
                        '_index': 'logstash-1',
                        '_source': {
                            'context': {
                                'deployment_id': 'dep_id'
                            },
                            'type': 'cloudify_log'
                        },
                        '_type': 'cloudify_log'
                    },
                    {
                        '_id': 'id_2',
                        '_index': 'logstash-1',
                        '_source': {
                            'context': {
                                'deployment_id': 'dep_id'
                            },
                            'type': 'cloudify_log'
                        },
                        '_type': 'cloudify_log'
                    },
                    {
                        '_id': 'id_3',
                        '_index': 'logstash-1',
                        '_source': {
                            'context': {
                                'deployment_id': 'dep_id'
                            },
                            'type': 'cloudify_log'
                        },
                        '_type': 'cloudify_log'
                    },
                    {
                        '_id': 'id_4',
                        '_index': 'logstash-1',
                        '_source': {
                            'context': {
                                'deployment_id': 'dep_id'
                            },
                            'type': 'cloudify_log'
                        },
                        '_type': 'cloudify_log'
                    },
                    {
                        '_id': 'id_5',
                        '_index': 'logstash-1',
                        '_source': {
                            'context': {
                                'deployment_id': 'dep_id'
                            },
                            'type': 'cloudify_log'
                        },
                        '_type': 'cloudify_log'
                                 ''}
                ],
                'total': 5}}

    def _sort_query_conditions_list(self, query):
        conditions = query['query']['filtered']['filter']['bool']['must']
        conditions.sort()

    def _get_expected_query(self):
        conditions = [
            {
                'query': {
                    'match': {
                        'context.blueprint_id': {
                            'query': 'some_blueprint',
                            'operator': 'and'
                        }
                    }
                }
            },
            {
                'query': {
                    'match': {
                        'context.deployment_id': {
                            'query': 'some_deployment',
                            'operator': 'and'
                        }
                    }
                }
            },
            {
                'terms': {
                    'type': ['cloudify_event', 'cloudify_logs']
                }
            },
            {
                'range': {
                    '@timestamp': {
                        'from': '2015-01-01T15:00:0',
                        'to': '2016-12-31T01:00:0'
                    }
                }
            }
        ]
        expected_query = {
            'query': {
                'filtered': {
                    'filter': {
                        'bool': {
                            'must': conditions
                        }
                    }
                }
            },
            'sort': [
                {
                    '@timestamp': {
                        'order': 'desc',
                        'ignore_unmapped': True
                    }
                }
            ],
            'size': 5,
            'from': 3
        }
        return expected_query

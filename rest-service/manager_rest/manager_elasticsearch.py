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
import elasticsearch
from flask import g, current_app as app

from manager_rest import config

DEFAULT_SEARCH_SIZE = 10000


# Singleton class
class ManagerElasticsearch:

    def __init__(self):
        pass

    @staticmethod
    def build_request_body(filters=None, pagination=None, skip_size=False,
                           sort=None, range_filters=None):
        """
        This method is used to create an elasticsearch request based on the
        Query DSL.
        It performs two actions:
        1. Based on the `filters` param passed to it, it builds a filter based
        query to only return elements that match the provided filters.
        Filters are faster than queries as they are cached and don't
        influence the score.
        2. Based on the `pagination` param, it sets the `size` and `from`
        parameters of the built query to make use of elasticsearch paging
        capabilities.

        :param filters: A dictionary containing filter keys and their expected
                        value.
        :param pagination: A dictionary with optional `size` and `offset`
                           keys.
        :param skip_size: If set to `True`, will not add `size` to the
                          body result.
        :param sort:    A dictionary containing sort keys and their order
                        ('asc' or 'desc')
        :param range_filters:   An optional dictionary where keys are fields
                        and values are the range limits of that field
        :return: An elasticsearch Query DSL body.
        """
        def _build_query_match_condition(k, v):
            return {"query": {"match":
                              {k: {"query": v, "operator": "and"}}}}

        mandatory_conditions = []
        body = {}

        if sort:
            body['sort'] = map(lambda k: {k: {"order": sort[k]}}, sort)

        if pagination:
            if not skip_size:
                body['size'] = pagination.get('size', DEFAULT_SEARCH_SIZE)
            if 'offset' in pagination:
                body['from'] = pagination['offset']
        elif not skip_size:
            body['size'] = DEFAULT_SEARCH_SIZE

        if filters:
            filter_conditions = []
            for key, val in filters.iteritems():
                if '.' in key:
                    # nested objects require special care...
                    # TODO: try to replace query_match with filter_term
                    query_condition = _build_query_match_condition(key, val)
                    filter_conditions.append(query_condition)
                else:
                    filter_type = 'terms' if isinstance(val, list) else 'term'
                    filter_conditions.append({filter_type: {key: val}})
            mandatory_conditions.extend(filter_conditions)

        if range_filters:
            range_conditions = \
                [{'range': {k: v} for k, v in range_filters.iteritems()}]
            mandatory_conditions.extend(range_conditions)

        if mandatory_conditions:
            body['query'] = {
                'filtered': {
                    'filter': {
                        'bool': {
                            'must': mandatory_conditions
                        }
                    }
                }
            }
        return body

    @staticmethod
    def get_connection():
        """Return a connection to Cloudify manager's Elasticsearch
        """
        if 'es_connection' not in g:
            es_host = config.instance().db_address
            es_port = config.instance().db_port
            g.es_connection = elasticsearch.Elasticsearch(
                hosts=[{"host": es_host, "port": es_port}])
        return g.es_connection

    @staticmethod
    def check_index_exists(index_name):
        if not hasattr(app, 'cloudify_events_index_exists'):
            es = ManagerElasticsearch.get_connection()
            app.cloudify_events_index_exists = \
                es.indices.exists(index=[index_name])
        return app.cloudify_events_index_exists

    @staticmethod
    def search(index=None, doc_type=None, body=None):
        """Query ElasticSearch with the provided index and query body.

        Returns:
        Elasticsearch result as is (Python dict).
        """
        es = ManagerElasticsearch.get_connection()
        return es.search(index=index, doc_type=doc_type, body=body)

    @staticmethod
    def build_list_result_metadata(query, search_result):

        pagination = {'total': search_result['hits']['total'],
                      'size': query.get('size'),
                      'offset': query.get('from')}
        metadata = {'pagination': pagination}
        return metadata

#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'ran'

import requests
import json
from requests.exceptions import HTTPError

STORAGE_INDEX_URL = "http://localhost:9200/cloudify_storage"

BLUEPRINT_SCHEMA = {
    'blueprint': {
        'properties': {
            'plan': {
                'enabled': False
            }
        }
    }
}

DEPLOYMENT_SCHEMA = {
    'deployment': {
        'properties': {
            'plan': {
                'enabled': False
            }
        }
    }
}

NODE_SCHEMA = {
    'node': {
        '_id': {
            'path': 'id'
        },
        'properties': {
            'types': {
                'type': 'string',
                'index_name': 'type'
            },
            'properties': {
                'enabled': False
            }
        }
    }
}

NODE_INSTANCE_SCHEMA = {
    'node_instance': {
        '_id': {
            'path': 'id'
        },
        'properties': {
            'runtimeProperties': {
                'enabled': False
            }
        }
    }
}


SETTINGS = {
    "settings": {
        "analysis": {
            "analyzer": {
                "default": {
                    "tokenizer": "whitespace"
                }
            }
        }
    }
}


def create_schema(storage_index_url):
    # making three tries, in case of communication errors with elasticsearch
    for _ in xrange(3):
        try:
            # delete index if already exist
            response = requests.head(storage_index_url)
            if response.status_code == 200:
                response = requests.delete(storage_index_url)
                response.raise_for_status()

            # create index
            response = requests.post(storage_index_url, data=json.dumps(
                SETTINGS))
            response.raise_for_status()

            # set mappings
            response = requests.put("{0}/blueprint/_mapping".format(
                storage_index_url), json.dumps(BLUEPRINT_SCHEMA))
            response.raise_for_status()
            response = requests.put("{0}/deployment/_mapping".format(
                storage_index_url), json.dumps(DEPLOYMENT_SCHEMA))
            response.raise_for_status()

            response = requests.put("{0}/node/_mapping".format(
                storage_index_url), json.dumps(NODE_SCHEMA))
            response.raise_for_status()

            response = requests.put("{0}/node_instance/_mapping".format(
                storage_index_url), json.dumps(NODE_INSTANCE_SCHEMA))
            response.raise_for_status()

            print 'Done creating elasticsearch storage schema.'
            break
        except HTTPError:
            pass


if __name__ == '__main__':
    create_schema(STORAGE_INDEX_URL)

    # from elasticsearch import Elasticsearch
    # e = Elasticsearch()
    # body = {
    #     'id': 'vm_node1',
    #     'deployment_id': 'my_dep',
    #     'types': ['cloudify.types.base', 'cloudify.types.host'],
    #     'properties': {
    #         'ip': '192.168.0.1'
    #     }
    # }
    # e.index('cloudify_storage', 'node', body, id=body['id'])
    # body = {
    #     'id': 'vm_node2',
    #     'deployment_id': 'my_dep-1',
    #     'types': ['cloudify.types.base', 'cloudify.types.database'],
    #     'properties': {
    #         'ip': ['111', '222']
    #     }
    # }
    # e.index('cloudify_storage', 'node', body, id=body['id'])
    # body = {
    #     'id': 'vm_node3',
    #     'deployment_id': 'my_dep-2',
    #     'types': ['cloudify.types.base', 'cloudify.types.web_server'],
    #     'properties': {
    #         'ip': {
    #             'network': 'my_network',
    #             'address': '192.168.0.1'
    #         }
    #     }
    # }
    # e.index('cloudify_storage', 'node', body, id=body['id'])


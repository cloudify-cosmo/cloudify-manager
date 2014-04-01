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


# DEPLOYMENT_SCHEMA = {
#     'deployment': {
#         'properties': {
#             'plan': {
#                 'properties': {
#                     'relationships': {
#                         'enabled': False
#                     },
#                     'name': {
#                         'enabled': True
#                     },
#                     'management_plugins_to_install': {
#                         'enabled': False
#                     },
#                     'is_management_plugins_to_install': {
#                         'enabled': False
#                     },
#                     'workflows': {
#                         'enabled': False
#                     },
#                     'nodes': {
#                         'enabled': False
#                         # 'properties': {
#                         #     'operations': {
#                         #         'enabled': True
#                         #     },
#                         #     'plugins': {
#                         #         'enabled': True
#                         #     },
#                         #     'declared_type': {
#                         #         'enabled': True
#                         #     },
#                         #     'name': {
#                         #         'enabled': True
#                         #     },
#                         #     'dependents': {
#                         #         'enabled': True
#                         #     },
#                         #     'id': {
#                         #         'enabled': True
#                         #     },
#                         #     'type': {
#                         #         'enabled': True
#                         #     },
#                         #     'host_id': {
#                         #         'enabled': True
#                         #     },
#                         #     'instances': {
#                         #         'enabled': True
#                         #     },
#                         #     'plugins_to_install': {
#                         #         'enabled': False
#                         #     },
#                         #     'management_plugins_to_install': {
#                         #         'enabled': False
#                         #     },
#                         #     'workflows': {
#                         #         'enabled': False
#                         #     },
#                         #     'properties': {
#                         #         'enabled': False
#                         #     },
#                         #     'relationships': {
#                         #         'properties': {
#                         #             'source_operations': {
#                         #                 'enabled': False
#                         #             },
#                         #             'target_operations': {
#                         #                 'enabled': False
#                         #             },
#                         #             'source_interfaces': {
#                         #                 'enabled': False
#                         #             },
#                         #             'target_interfaces': {
#                         #                 'enabled': False
#                         #             },
#                         #             'workflows': {
#                         #                 'enabled': False
#                         #             },
#                         #             'target_id': {
#                         #                 'enabled': True
#                         #             },
#                         #             'type': {
#                         #                 'enabled': True
#                         #             }
#                         #         }
#                         #     }
#                         # }
#                     }
#                 }
#             }
#         }
#     }
# }


def create_schema(storage_index_url):
    # delete index if already exist
    response = requests.head(storage_index_url)
    if response.status_code == 200:
        response = requests.delete(storage_index_url)
        response.raise_for_status()

    # create index
    response = requests.post(storage_index_url, data=json.dumps(SETTINGS))
    response.raise_for_status()

    # set mappings
    response = requests.put("{0}/blueprint/_mapping".format(
        storage_index_url), json.dumps(BLUEPRINT_SCHEMA))
    response.raise_for_status()
    response = requests.put("{0}/deployment/_mapping".format(
        storage_index_url), json.dumps(DEPLOYMENT_SCHEMA))
    response.raise_for_status()
    print 'Done creating elasticsearch storage schema.'


if __name__ == '__main__':
    create_schema(STORAGE_INDEX_URL)

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

# DEPLOYMENT_SCHEMA = {
#     'deployment': {
#         'properties': {
#             'plan': {
#                 'enabled': False
#             }
#         }
#     }
# }
#
# BLUEPRINT_SCHEMA = {
#     'blueprint': {
#         'properties': {
#             'plan': {
#                 'enabled': False
#             }
#         }
#     }
# }


def main():
    #delete index if already exist
    response = requests.head(STORAGE_INDEX_URL)
    if response.status_code == 200:
        response = requests.delete(STORAGE_INDEX_URL)
        response.raise_for_status()

    #create index
    response = requests.post(STORAGE_INDEX_URL, data={})
    response.raise_for_status()

    #set mappings
    response = requests.put("{0}/blueprint/_mapping".format(
        STORAGE_INDEX_URL), json.dumps(BLUEPRINT_SCHEMA))
    response.raise_for_status()
    response = requests.put("{0}/deployment/_mapping".format(
        STORAGE_INDEX_URL), json.dumps(DEPLOYMENT_SCHEMA))
    response.raise_for_status()
    print 'Done creating elasticsearch storage schema.'


if __name__ == '__main__':
    main()
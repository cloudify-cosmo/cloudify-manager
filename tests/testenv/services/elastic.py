########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import time
import sys
import os

from elasticsearch.client import IndicesClient

from testenv import utils

STORAGE_INDEX_NAME = 'cloudify_storage'

logger = utils.setup_logger('elasticsearch_process')


def _remove_index_if_exists():
    es = utils.create_es_client()
    es_index = IndicesClient(es)
    if es_index.exists(STORAGE_INDEX_NAME):
        logger.info(
            "Elasticsearch index '{0}' already exists and "
            "will be deleted".format(STORAGE_INDEX_NAME))
        try:
            es_index.delete(STORAGE_INDEX_NAME)
            logger.info('Verifying Elasticsearch index was deleted...')
            deadline = time.time() + 45
            while es_index.exists(STORAGE_INDEX_NAME):
                if time.time() > deadline:
                    raise RuntimeError(
                        'Elasticsearch index was not deleted after '
                        '30 seconds')
                time.sleep(0.5)
        except BaseException as e:
            logger.warn('Ignoring caught exception on Elasticsearch delete'
                        ' index - {0}: {1}'.format(e.__class__, e.message))


def _create_schema():
    from testenv import es_schema_creator
    creator_script_path = es_schema_creator.__file__
    cmd = '{0} {1}'.format(sys.executable, creator_script_path)
    status = os.system(cmd)
    if status != 0:
        raise RuntimeError(
            'Elasticsearch create schema exited with {0}'.format(status))
    logger.info("Elasticsearch schema created successfully")


def reset_data():
    _remove_index_if_exists()
    _create_schema()

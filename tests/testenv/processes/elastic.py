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

import logging
import re
import shlex
import subprocess
import time
import sys
import os
import elasticsearch

from cloudify.utils import setup_logger
from testenv.constants import STORAGE_INDEX_NAME
from testenv.constants import LOG_INDICES_PREFIX


logger = setup_logger('elasticsearch_process')


class ElasticSearchProcess(object):
    """
    Manages an ElasticSearch server process lifecycle.
    """

    def __init__(self):
        self._pid = None
        self._process = None
        setup_logger('elasticsearch',
                     logging.INFO)
        setup_logger('elasticsearch.trace',
                     logging.INFO)

    @staticmethod
    def _verify_service_responsiveness(timeout=120):
        import urllib2
        service_url = "http://localhost:9200"
        up = False
        deadline = time.time() + timeout
        res = None
        while time.time() < deadline:
            try:
                res = urllib2.urlopen(service_url)
                up = res.code == 200
                break
            except BaseException as e:
                if e.message:
                    logger.warning(e.message)
                pass
            time.sleep(0.5)
        if not up:
            raise RuntimeError("Elasticsearch service is not responding @ {"
                               "0} (response: {1})".format(service_url, res))

    def _verify_service_started(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self._pid = self._get_service_pid()
            if self._pid is not None:
                break
            time.sleep(0.5)
        if self._pid is None:
            raise RuntimeError("Failed to start elasticsearch service within "
                               "a {0} seconds timeout".format(timeout))

    def _verify_service_ended(self, timeout=10):
        pid = self._pid
        deadline = time.time() + timeout
        while time.time() < deadline:
            pid = self._get_service_pid()
            if pid is None:
                break
            time.sleep(0.5)
        if pid is not None:
            raise RuntimeError("Failed to stop elasticsearch service within "
                               "a {0} seconds timeout".format(timeout))

    @staticmethod
    def _get_service_pid():
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output(
                "ps -ef | grep elasticsearch | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None

    def start(self):
        command = 'elasticsearch'
        logger.info('Starting elasticsearch service with command {0}'
                    .format(command))
        self._add_append_script()
        self._process = subprocess.Popen(shlex.split(command))
        self._verify_service_started()
        self._verify_service_responsiveness()
        logger.info('elasticsearch service started [pid=%s]', self._pid)
        self.reset_data()

    def close(self):
        if self._pid:
            logger.info('Shutting down elasticsearch service [pid=%s]',
                        self._pid)
            os.system('kill {0}'.format(self._pid))
            self._verify_service_ended()

    def reset_data(self):
        self._remove_index_if_exists()
        self._create_schema()

    @staticmethod
    def remove_log_indices():
        es = elasticsearch.Elasticsearch()
        from elasticsearch.client import IndicesClient
        es_index = IndicesClient(es)
        log_index_pattern = '{0}*'.format(LOG_INDICES_PREFIX)
        if es_index.exists(log_index_pattern):
            logger.info(
                "Elasticsearch indices '{0}' already exist and "
                "will be deleted".format(log_index_pattern))
            try:
                es_index.delete(log_index_pattern)
                logger.info('Verifying Elasticsearch index was deleted...')
                deadline = time.time() + 45
                while es_index.exists(log_index_pattern):
                    if time.time() > deadline:
                        raise RuntimeError(
                            'Elasticsearch index was not deleted after '
                            '30 seconds')
                    time.sleep(0.5)
            except BaseException as e:
                logger.warn('Ignoring caught exception on Elasticsearch delete'
                            ' index - {0}: {1}'.format(e.__class__, e.message))

    @staticmethod
    def _remove_index_if_exists():
        es = elasticsearch.Elasticsearch()
        from elasticsearch.client import IndicesClient
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

    @staticmethod
    def _create_schema():
        from testenv import es_schema_creator
        creator_script_path = es_schema_creator.__file__
        cmd = '{0} {1}'.format(sys.executable, creator_script_path)
        status = os.system(cmd)
        if status != 0:
            raise RuntimeError(
                'Elasticsearch create schema exited with {0}'.format(status))
        logger.info("Elasticsearch schema created successfully")

    @staticmethod
    def _add_append_script():
        """
        write the 'append to list' ES script to a file and store it at
        ES scripts path (<ES>/config/scripts)
        """

        # get elasticsearch base dir and resolve script file destination
        es_path = os.path.dirname(
            os.path.dirname(
                subprocess.check_output('which elasticsearch',
                                        shell=True).rstrip('\r\n')))
        es_scripts_path = os.path.join(es_path, 'config/scripts')
        script_path = os.path.join(es_scripts_path, 'append.groovy')

        if os.path.exists(script_path):
            return

        use_sudo = os.environ.get('CI') == 'true'
        script = ('if (ctx._source.containsKey(key))'
                  ' {ctx._source[key] += value;}'
                  ' else {ctx._source[key] = [value]}').replace('"', r'\"')

        if not os.path.exists(es_scripts_path):
            os.system('{0} mkdir -p {1}'.format(
                'sudo' if use_sudo else '',
                es_scripts_path))

        os.system('echo "{0}" | {1} tee {2}'.format(
            script,
            'sudo' if use_sudo else '',
            script_path
        ))

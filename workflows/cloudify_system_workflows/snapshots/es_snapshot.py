########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import json
import utils
from datetime import datetime

from elasticsearch import helpers as elasticsearch_helpers

from cloudify.workflows import ctx

from .constants import M_HAS_CLOUDIFY_EVENTS


class ElasticSearch(object):
    _ELASTICSEARCH = 'es_data'
    _EVENTS_INDEX_NAME = 'cloudify_events'

    @staticmethod
    def restore_db_from_pre_4_version(tempdir, tenant_name):
        ctx.logger.info('Restoring DB from version prior to 4 (Elastic)')
        python_bin = '/opt/manager/env/bin/python'
        dir_path = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(dir_path, 'estopg.py')
        es_dump_path = os.path.join(tempdir, 'es_data')
        command = [python_bin, script_path, es_dump_path, tenant_name]
        result = utils.run(command)
        if result and hasattr(result, 'aggr_stdout'):
            ctx.logger.debug('Process result: \n{0}'
                             .format(result.aggr_stdout))

    def restore_logs_and_events(self,
                                es,
                                tempdir,
                                metadata,
                                bulk_read_timeout):
        manager_has_cloudify_events = self._manager_has_cloudify_events(es)
        snapshot_has_cloudify_events = metadata[M_HAS_CLOUDIFY_EVENTS]
        data_iter = self._get_iterator(
            tempdir,
            manager_has_cloudify_events,
            snapshot_has_cloudify_events
        )

        try:
            first = next(data_iter)
        except StopIteration:
            # no elements to restore
            return

        def not_empty_data_iter():
            yield first
            for e in data_iter:
                yield e

        elasticsearch_helpers.bulk(es,
                                   not_empty_data_iter(),
                                   request_timeout=bulk_read_timeout)
        es.indices.flush()

    def _get_iterator(self,
                      tempdir,
                      manager_has_cloudify_events,
                      snapshot_has_cloudify_events):
        """Get a data iterator based on whether the manager/snapshot have
        cloudify events and/or logstash
        """
        if (manager_has_cloudify_events and snapshot_has_cloudify_events) or\
                (not manager_has_cloudify_events and
                 not snapshot_has_cloudify_events):
            # Both manager and snapshot have events only in ES/logstash
            return self._get_data_iter(tempdir)
        elif not snapshot_has_cloudify_events and manager_has_cloudify_events:
            # Manager has events in ES but the snapshot does not
            return self._logstash_to_cloudify_events(tempdir)
        else:
            # Snapshot has events in ES but the manager does not
            return self._cloudify_events_to_logstash(tempdir)

    @staticmethod
    def _manager_has_cloudify_events(es):
        return es.indices.exists(index=ElasticSearch._EVENTS_INDEX_NAME)

    def _get_data_iter(self, tempdir):
        """Iterate over ES dump in the snapshot archive

        :param tempdir: The directory of the archive
        """
        for line in open(os.path.join(tempdir, self._ELASTICSEARCH), 'r'):
            elem = json.loads(line)
            yield elem

    def _logstash_to_cloudify_events(self, tempdir):
        """Convert objects from the default iterator from the logstash format
        to the ES format
        """
        for elem in self._get_data_iter(tempdir):
            if elem['_index'].startswith('logstash-'):
                elem['_index'] = self._EVENTS_INDEX_NAME
            yield elem

    def _cloudify_events_to_logstash(self, tempdir):
        """Convert objects from the default iterator from the es format
        to the logstash format
        """
        d = datetime.now()
        index = 'logstash-{0}'.format(d.strftime('%Y.%m.%d'))
        for elem in self._get_data_iter(tempdir):
            if elem['_index'] == self._EVENTS_INDEX_NAME:
                elem['_index'] = index
            yield elem

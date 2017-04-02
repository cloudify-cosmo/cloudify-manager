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
import shutil
import pickle

from cloudify.workflows import ctx
from cloudify.exceptions import NonRecoverableError

from .utils import is_compute, copy as copy_file


class Credentials(object):
    _CRED_DIR = 'snapshot-credentials'
    _CRED_KEY_NAME = 'agent_key'

    def restore(self, tempdir, postgres):
        self._postgres = postgres
        dump_cred_dir = os.path.join(tempdir, self._CRED_DIR)
        if not os.path.isdir(dump_cred_dir):
            ctx.logger.info('Missing credentials dir: '
                            '{0}'.format(dump_cred_dir))
            return
        restored_cred_dir = self._create_restored_cred_dir()
        agent_key_path_dict = self._create_agent_key_path_dict()

        for dep_node_id in os.listdir(dump_cred_dir):
            self._restore_agent_credentials(
                dep_node_id,
                dump_cred_dir,
                restored_cred_dir,
                agent_key_path_dict
            )

    def dump(self, tempdir):
        archive_cred_path = os.path.join(tempdir, self._CRED_DIR)
        ctx.logger.debug('Dumping credentials data, '
                         'archive_cred_path: {0}'.format(archive_cred_path))
        os.makedirs(archive_cred_path)

        for deployment_id, n in self._get_hosts():
            props = n.properties
            if 'cloudify_agent' in props and 'key' in props['cloudify_agent']:
                node_id = deployment_id + '_' + n.id
                agent_key_path = props['cloudify_agent']['key']
                self._dump_agent_key(
                    node_id,
                    agent_key_path,
                    archive_cred_path
                )

    @staticmethod
    def _get_hosts():
        return [(deployment_id, node)
                for deployment_id, wctx in ctx.deployments_contexts.iteritems()
                for node in wctx.nodes
                if is_compute(node)]

    def _dump_agent_key(self, node_id, agent_key_path, archive_cred_path):
        """Copy an agent key from its location on the manager to the snapshot
        dump
        """
        os.makedirs(os.path.join(archive_cred_path, node_id))
        source = os.path.expanduser(agent_key_path)
        destination = os.path.join(archive_cred_path, node_id,
                                   self._CRED_KEY_NAME)
        ctx.logger.debug('Dumping credentials data, '
                         'copy from: {0} to {1}'
                         .format(source, destination))
        shutil.copy(source, destination)

    def _restore_agent_credentials(self,
                                   dep_node_id,
                                   dump_cred_dir,
                                   restored_cred_dir,
                                   agent_key_path_dict):
        restored_agent_key_path = \
            self._restore_agent_key_from_dump(dump_cred_dir,
                                              restored_cred_dir,
                                              dep_node_id)
        db_agent_key_path = agent_key_path_dict[dep_node_id]

        if os.path.isfile(db_agent_key_path):
            self._handle_existing_agent_key_path(
                restored_agent_key_path,
                db_agent_key_path
            )
        else:
            copy_file(restored_agent_key_path, db_agent_key_path)

    @staticmethod
    def _handle_existing_agent_key_path(restored_key_path,
                                        db_key_path):
        """Handle the case where the agent key already exists; either ignore
        it if the contents are identical, or raise an error if they aren't

        :param restored_key_path: The key path as restored from the dump
        :param db_key_path: The key path as retrieved from the DB
        """
        with open(db_key_path) as key_file:
                content_1 = key_file.read()
        with open(restored_key_path) as key_file:
            content_2 = key_file.read()
        if content_1 != content_2:
            raise NonRecoverableError(
                'Agent key path already taken: {0}'.format(db_key_path)
            )
        ctx.logger.debug('Agent key path already exist: '
                         '{0}'.format(db_key_path))

    @staticmethod
    def _create_restored_cred_dir():
        """Create a new directory for agent key paths
        """
        restored_cred_dir = os.path.join('/opt/manager', Credentials._CRED_DIR)
        if os.path.exists(restored_cred_dir):
            shutil.rmtree(restored_cred_dir)
        os.makedirs(restored_cred_dir)
        return restored_cred_dir

    @staticmethod
    def _restore_agent_key_from_dump(dump_cred_dir,
                                     restored_cred_dir,
                                     deployment_node_id):
        """Restore the agent key from the snapshot dump and return its path

        :param dump_cred_dir: Key path directory in the snapshot dump
        :param restored_cred_dir: Key path directory on the manager
        :param deployment_node_id:
        :return: The local path of the agent key
        """
        os.makedirs(os.path.join(restored_cred_dir, deployment_node_id))
        agent_key_path = os.path.join(restored_cred_dir,
                                      deployment_node_id,
                                      Credentials._CRED_KEY_NAME)
        agent_key_path_in_dump = os.path.join(dump_cred_dir,
                                              deployment_node_id,
                                              Credentials._CRED_KEY_NAME)
        shutil.copy(agent_key_path_in_dump, agent_key_path)
        return agent_key_path

    def _get_node_properties_query_result(self):
        """Create an SQL query that retrieves node properties from the DB
        :return: A list of tuples - each has three elements:
        1. Deployment ID
        2. Node Id
        3. The pickled properties dict
        """
        query = "SELECT nodes.id, deployments.id, properties " \
                "FROM nodes JOIN deployments " \
                "ON nodes._deployment_fk = deployments._storage_id;"
        return self._postgres.run_query(query)['all']

    @staticmethod
    def _get_agent_config(node_properties):
        """cloudify_agent is deprecated, but still might be used in older
        systems, so we try to gather the agent config from both sources
        """
        cloudify_agent = node_properties.get('cloudify_agent', {})
        agent_config = node_properties.get('agent_config', {})
        agent_config.update(cloudify_agent)
        return agent_config

    def _create_agent_key_path_dict(self):
        agent_key_path_dict = dict()
        result = self._get_node_properties_query_result()
        for elem in result:
            node_id = elem[0]
            deployment_id = elem[1]
            node_properties = pickle.loads(elem[2])
            agent_config = self._get_agent_config(node_properties)
            if 'key' in agent_config:
                agent_key_path = agent_config['key']
                key = deployment_id + '_' + node_id
                agent_key_path_dict[key] = os.path.expanduser(agent_key_path)
        return agent_key_path_dict

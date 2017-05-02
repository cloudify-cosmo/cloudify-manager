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
import pickle
import shutil
import string
import subprocess

from cloudify.workflows import ctx
from cloudify_rest_client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from .constants import SECRET_STORE_AGENT_KEY_PREFIX
from .utils import is_compute


ALLOWED_KEY_CHARS = string.ascii_letters + string.digits + '-._'


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
        agent_key_path_dict = self._create_agent_key_path_dict()

        for dep_node_id in os.listdir(dump_cred_dir):
            self._restore_agent_credentials(
                dep_node_id,
                dump_cred_dir,
                agent_key_path_dict,
            )

    def dump(self, tempdir):
        archive_cred_path = os.path.join(tempdir, self._CRED_DIR)
        ctx.logger.debug('Dumping credentials data, '
                         'archive_cred_path: {0}'.format(archive_cred_path))
        os.makedirs(archive_cred_path)

        for deployment_id, n in self._get_hosts():
            props = n.properties
            agent_config = self._get_agent_config(props)
            if 'key' in agent_config:
                node_id = deployment_id + '_' + n.id
                agent_key_path = agent_config['key']
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

    def _restore_agent_credentials(
            self,
            dep_node_id,
            dump_cred_dir,
            agent_key_path_dict,
            ):
        agent_key_path_in_dump = os.path.join(dump_cred_dir,
                                              dep_node_id,
                                              Credentials._CRED_KEY_NAME)

        with open(agent_key_path_in_dump) as f:
            key_data = f.read()

        for tenant, path in agent_key_path_dict[dep_node_id].items():
            db_agent_key_path = agent_key_path_dict[dep_node_id][tenant]
            key_name = add_key_secret(tenant, db_agent_key_path, key_data)

            subprocess.check_call(
                [
                    'sudo', '-u', 'cloudify-restservice',
                    '/opt/mgmtworker/resources/cloudify/fix_snapshot_ssh_db',
                    tenant, db_agent_key_path, key_name,
                ],
            )

    def _get_node_properties_query_result(self):
        """Create an SQL query that retrieves node properties from the DB
        :return: A list of tuples - each has 4 elements:
        0. Deployment ID
        1. Node Id
        2. The pickled properties dict
        3. The tenant which owns the deployment
        """
        query = """
            SELECT nodes.id, deployments.id, properties, tenants.name
            FROM nodes
            JOIN deployments
            ON nodes._deployment_fk = deployments._storage_id
            JOIN tenants
            ON deployments._tenant_id = tenants.id
            ;"""
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
            tenant = elem[3]
            if 'key' in agent_config:
                agent_key_path = agent_config['key']
                key = deployment_id + '_' + node_id
                agent_key_path_dict.setdefault(
                    key, {})[tenant] = os.path.expanduser(agent_key_path)
        return agent_key_path_dict


def add_key_secret(tenant, key_path, key_data):
    key_name = SECRET_STORE_AGENT_KEY_PREFIX + ''.join(
        char if char in ALLOWED_KEY_CHARS else '_'
        for char in key_path
        )

    client = CloudifyClient(
        'localhost',
        token=ctx.rest_token,
        tenant=tenant,
    )
    secrets = client.secrets

    while True:
        try:
            secret_value = secrets.get(key_name)
        except CloudifyClientError as e:
            if e.status_code == 404 and 'not found' in str(e):
                secrets.create(key_name, key_data)
                break
            else:
                raise
        if secret_value == key_data:
            break

    return key_name

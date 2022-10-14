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
import re
import pickle
import shutil
import string
import itertools

from cloudify.manager import get_rest_client
from cloudify.workflows import ctx

from .constants import V_4_1_0, SECRET_STORE_AGENT_KEY_PREFIX
from .utils import is_compute, run, get_tenants_list

ALLOWED_KEY_CHARS = string.ascii_letters + string.digits + '-._'
CRED_DIR = 'snapshot-credentials'
DEPLOYMENTS_QUERY = """
    SELECT nodes.id, deployments.id, properties
    FROM nodes
    JOIN deployments
    ON nodes._deployment_fk = deployments._storage_id
    JOIN tenants
    ON deployments._tenant_id = tenants.id
    WHERE tenants.name = %(tenant)s
    ;
"""


class Credentials(object):
    _CRED_KEY_NAME = 'agent_key'
    _ARCHIVE_CRED_PATH = None

    def dump(self, tempdir, version):
        self._ARCHIVE_CRED_PATH = os.path.join(tempdir, CRED_DIR)
        ctx.logger.debug('Dumping credentials data, archive_cred_path: '
                         '{0}'.format(self._ARCHIVE_CRED_PATH))
        os.makedirs(self._ARCHIVE_CRED_PATH)

        for tenant, dep_id, node in self._get_hosts(version):
            agent_config = get_agent_config(node.properties)
            agent_key = agent_config.get('key')
            # Don't do anything with empty or {get_secret} agent keys
            if agent_key and isinstance(agent_key, str):
                agent_dirname = _get_agent_dirname(
                    version, tenant, dep_id, node.id
                )
                self._dump_agent_key(agent_dirname, agent_key)

    @staticmethod
    def _get_hosts(version):
        """Find host nodes, and yield (tenant_name, dep_id, node)"""
        tenants = get_tenants_list(version)
        for tenant_name in tenants:
            client = get_rest_client(tenant_name)
            deployments = client.deployments.list(
                _include=['id'],
                _get_all_results=True
            )
            for deployment in deployments:
                nodes = client.nodes.list(
                    deployment_id=deployment.id,
                    _get_all_results=True
                )
                for node in nodes:
                    if is_compute(node):
                        yield tenant_name, deployment.id, node

    def _dump_agent_key(self, agent_dirname, agent_key):
        """Copy an agent key from its location on the manager to the snapshot
        dump
        """
        os.makedirs(os.path.join(self._ARCHIVE_CRED_PATH, agent_dirname))
        source = os.path.expanduser(agent_key)
        destination = os.path.join(self._ARCHIVE_CRED_PATH, agent_dirname,
                                   self._CRED_KEY_NAME)
        ctx.logger.debug('Dumping credentials data, '
                         'copy from: {0} to {1}'
                         .format(source, destination))
        try:
            shutil.copy(source, destination)
        except Exception as e:
            ctx.logger.debug(
                "Key doesn't appear to be a file path. Skipping ({})".format(
                    e))


def get_agent_config(node_properties):
    """cloudify_agent is deprecated, but still might be used in older
    systems, so we try to gather the agent config from both sources
    """
    agent_config = node_properties.get('cloudify_agent', {})
    agent_config.update(node_properties.get('agent_config', {}))
    return agent_config


def candidate_key_names(path):
    filtered = SECRET_STORE_AGENT_KEY_PREFIX + ''.join(
        char if char in ALLOWED_KEY_CHARS else '_'
        for char in path
        )
    yield filtered
    for suffix in itertools.count(1):
        yield '{name}_{suffix}'.format(name=filtered, suffix=suffix)


def _fix_snapshot_ssh_db(tenant, orig, replace):
    python_bin = '/opt/manager/env/bin/python'
    dir_path = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(dir_path, 'fix_snapshot_ssh_db.py')
    command = [python_bin, script_path, tenant, orig, replace]
    res = run(command)
    if res and hasattr(res, 'aggr_stdout'):
        ctx.logger.debug('Process result: \n{0}'
                         .format(res.aggr_stdout))


def _get_agent_dirname(version, tenant, dep_id, node_id):
    if version >= V_4_1_0:
        return '{tenant}_{dep_id}_{node_id}'.format(
            tenant=tenant, dep_id=dep_id, node_id=node_id
        )
    else:
        return '{dep_id}_{node_id}'.format(dep_id=dep_id, node_id=node_id)


def restore(tempdir, postgres, version):
    dump_cred_dir = os.path.join(tempdir, CRED_DIR)
    if not os.path.isdir(dump_cred_dir):
        ctx.logger.info('Missing credentials dir: '
                        '{0}'.format(dump_cred_dir))
        return

    credential_dirs = set(os.listdir(dump_cred_dir))

    for tenant in get_tenants_list(version):
        client = get_rest_client(tenant=tenant)

        # !! mapping key CONTENTS to their secret store keys
        key_secrets = {}
        secret_keys = set()
        secrets_list = client.secrets.list(_include=['key'],
                                           _get_all_results=True)
        for secret in secrets_list:
            if secret.key.startswith(SECRET_STORE_AGENT_KEY_PREFIX):
                secret = client.secrets.get(secret.key)
                key_secrets[secret.value] = secret.key
                secret_keys.add(secret.key)

        new_key_secrets = {}
        replacements = {}

        result = postgres.run_query(
            DEPLOYMENTS_QUERY,
            {'tenant': tenant},
        )['all']

        for elem in result:
            node_id = elem[0]
            deployment_id = elem[1]
            node_properties = pickle.loads(elem[2])
            agent_config = get_agent_config(node_properties)
            agent_key = agent_config.get('key')

            if not agent_key:
                continue

            dir_name = _get_agent_dirname(version,
                                          tenant,
                                          deployment_id,
                                          node_id)

            if not isinstance(agent_key, str):
                ctx.logger.info('key for {} is not a path'.format(dir_name))
                continue
            if re.search('BEGIN .* PRIVATE KEY', agent_key):
                ctx.logger.info('key for {} is bare key'.format(dir_name))
                continue
            if dir_name not in credential_dirs:
                continue

            agent_key_path_in_dump = os.path.join(
                dump_cred_dir,
                dir_name,
                'agent_key',
                )
            try:
                with open(agent_key_path_in_dump) as f:
                    key_data = f.read()
            except IOError as e:
                if e.errno == os.errno.ENOENT:
                    ctx.logger.info(
                        'key file for {} not found'.format(dir_name))
                    continue
                raise

            # We've probably found the right key!

            if key_data not in key_secrets:
                # If we got here, we need to create a secret
                for key in candidate_key_names(agent_key):
                    if key not in secret_keys:
                        new_key_secrets[key] = key_data
                        key_secrets[key_data] = key
                        secret_keys.add(key)
                        break

            replacements[agent_key] = key_secrets[key_data]

        for key, value in new_key_secrets.items():
            client.secrets.create(key, value)

        for orig, replace in replacements.items():
            _fix_snapshot_ssh_db(tenant, orig, replace)

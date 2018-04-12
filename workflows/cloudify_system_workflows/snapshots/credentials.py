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
import json
import pickle
import shutil
import string
import itertools

from cloudify.manager import get_rest_client
from cloudify.workflows import ctx

from .utils import is_compute, run, get_dep_contexts, get_tenants_list
from .constants import (V_4_1_0,
                        SECURITY_FILE_LOCATION,
                        SECRET_STORE_AGENT_KEY_PREFIX)

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

        for tenant, value in self._get_hosts(version):
            for dep_id, nodes in value.iteritems():
                for node in nodes:
                    agent_config = get_agent_config(node.properties)
                    agent_key = agent_config.get('key')
                    # Don't do anything with empty or {get_secret} agent keys
                    if agent_key and isinstance(agent_key, basestring):
                        agent_dirname = _get_agent_dirname(
                            version, tenant, dep_id, node.id
                        )
                        self._dump_agent_key(agent_dirname, agent_key)

    @staticmethod
    def _get_hosts(version):
        """
        Return a dict with tenants as keys, and dicts as values, in which
        deployment IDs are keys and a list of nodes is the value
        """
        hosts = {}
        for tenant, deployments in get_dep_contexts(version):
            for deployment_id, dep_ctx in deployments.iteritems():
                for node in dep_ctx.nodes:
                    if is_compute(node):
                        tenant_hosts = hosts.setdefault(tenant, {})
                        deps = tenant_hosts.setdefault(deployment_id, [])
                        deps.append(node)
        return hosts.iteritems()

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

    for tenant in get_tenants_list():
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

            if not isinstance(agent_key, basestring):
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

        encryption_key = _get_encryption_key() if new_key_secrets else None
        for key, value in new_key_secrets.items():
            # The encryption_key parameter is used internally only
            # when we create the agent's ssh keys as secrets during snapshot
            # restore. We need to use the encryption key from the snapshot
            # so after the snapshot restore these secrets can be decrypted
            client.secrets.create(key, value, encryption_key=encryption_key)

        for orig, replace in replacements.items():
            _fix_snapshot_ssh_db(tenant, orig, replace)


def _get_encryption_key():
    # The encryption_key (from the snapshot) is updated in rest-security.conf
    # file but not yet loaded to the config
    with open(SECURITY_FILE_LOCATION) as security_conf_file:
        rest_security_conf = json.load(security_conf_file)
    return rest_security_conf['encryption_key']

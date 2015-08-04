import json
import tempfile
import time
import shutil
import zipfile

from itertools import chain
from os import (path, makedirs, remove, listdir)
from subprocess import call

import elasticsearch
import elasticsearch.helpers

from cloudify.decorators import system_wide_workflow

VERSION = '3.3'
VERSION_FILE = 'version'
ELASTICSEARCH = 'es_data'
CRED_DIR = 'credentials'
CRED_KEY_NAME = 'agent_key'
INFLUXDB = 'influxdb-data'
INFLUXDB_DUMP_CMD = ('curl -s -G "http://localhost:8086/db/cloudify/series'
                     '?u=root&p=root&chunked=true" --data-urlencode'
                     ' "q=select * from /.*/" > {0}')
INFLUXDB_RESTORE_CMD = ('cat {0} | while read -r line; do curl -X POST '
                        '-d "[${{line}}]" "http://localhost:8086/db/cloudify/'
                        'series?u=root&p=root" ;done')


class DictToAttributes(object):
    def __init__(self, dic):
        self._dict = dic

    def __getattr__(self, name):
        return self._dict[name]


def get_json_objects(f):
    def chunks(g):
        ch = g.read(10000)
        yield ch
        while ch:
            ch = g.read(10000)
            yield ch

    s = ''
    decoder = json.JSONDecoder()
    for ch in chunks(f):
        s += ch
        try:
            while s:
                obj, idx = decoder.raw_decode(s)
                yield json.dumps(obj)
                s = s[idx:]
        except:
            pass

    assert not s


def copy_data(archive_root, config, to_archive=True):
    DATA_TO_COPY = [
        (config.file_server_blueprints_folder, 'blueprints'),
        (config.file_server_uploaded_blueprints_folder, 'uploaded-blueprints')
    ]

    # files with constant relative/absolute paths
    for (p1, p2) in DATA_TO_COPY:
        if p1[0] != '/':
            p1 = path.join(config.file_server_root, p1)
        if p2[0] != '/':
            p2 = path.join(archive_root, p2)
        if not to_archive:
            p1, p2 = p2, p1

        if not path.exists(p1):
            continue

        if path.isfile(p1):
            shutil.copy(p1, p2)
        else:
            if path.exists(p2):
                shutil.rmtree(p2, ignore_errors=True)
            shutil.copytree(p1, p2)


def _create_es_client(config):
    return elasticsearch.Elasticsearch(hosts=[{'host': config.db_address,
                                               'port': config.db_port}])


def _except_types(s, *args):
    return (e for e in s if e['_type'] not in args)


def _delete_all_docs_except_context(es_client):
    s = elasticsearch.helpers.scan(es_client)
    for doc in _except_types(s, 'provider_context'):
        doc['_op_type'] = 'delete'
        yield doc


@system_wide_workflow
def create(ctx, snapshot_id, config, **kw):
    config = DictToAttributes(config)
    tempdir = tempfile.mkdtemp('-snapshot-data')

    snapshots_dir = path.join(
        config.file_server_root,
        config.file_server_uploaded_snapshots_folder
    )

    # files/dirs copy
    copy_data(tempdir, config)

    # elasticsearch
    es = _create_es_client(config)
    storage_scan = elasticsearch.helpers.scan(es, index='cloudify_storage')
    storage_scan = _except_types(storage_scan, 'provider_context')
    event_scan = elasticsearch.helpers.scan(es, index='cloudify_events')

    with open(path.join(tempdir, ELASTICSEARCH), 'w') as f:
        for item in chain(storage_scan, event_scan):
            f.write(json.dumps(item) + '\n')

    # influxdb
    influxdb_file = path.join(tempdir, INFLUXDB)
    influxdb_temp_file = influxdb_file + '.temp'
    call(INFLUXDB_DUMP_CMD.format(influxdb_temp_file), shell=True)
    with open(influxdb_temp_file, 'r') as f, open(influxdb_file, 'w') as g:
        for obj in get_json_objects(f):
            g.write(obj + '\n')

    remove(influxdb_temp_file)

    # credentials
    archive_cred_path = path.join(tempdir, CRED_DIR)
    makedirs(archive_cred_path)

    node_scan = elasticsearch.helpers.scan(es, index='cloudify_storage',
                                           doc_type='node')
    for n in node_scan:
        props = n['_source']['properties']
        if 'cloudify_agent' in props:
            node_id = n['_id']
            agent_key_path = props['cloudify_agent']['key']
            makedirs(path.join(archive_cred_path, node_id))
            shutil.copy(path.expanduser(agent_key_path),
                        path.join(archive_cred_path, node_id, CRED_KEY_NAME))

    # version
    with open(path.join(tempdir, VERSION_FILE), 'w') as f:
        f.write(VERSION)

    # zip
    snapshot_dir = path.join(snapshots_dir, snapshot_id)
    makedirs(snapshot_dir)

    zipf = shutil.make_archive(
        path.join(snapshot_dir, snapshot_id),
        'zip',
        tempdir
    )

    # end
    shutil.rmtree(tempdir)
    created_at = time.strftime('%d %b %Y %H:%M:%S',
                               time.localtime(path.getctime(zipf)))

    return {
        'id': snapshot_id,
        'created_at': created_at
    }


def restore_snapshot_format_3_3(ctx, config, tempdir):

    # files/dirs copy
    copy_data(tempdir, config, to_archive=False)

    # elasticsearch
    es = _create_es_client(config)

    this_exec = es.get(id=ctx.execution_id, index='cloudify_storage',
                       doc_type='execution')

    ctx.send_event('Deleting all ElasticSearch data')
    elasticsearch.helpers.bulk(es, _delete_all_docs_except_context(es))
    es.indices.flush()

    def es_data_itr():
        for line in open(path.join(tempdir, ELASTICSEARCH), 'r'):
            yield json.loads(line)
        this_exec['_version'] = None
        del this_exec['found']
        yield this_exec

    ctx.send_event('Restoring ElasticSearch data')
    elasticsearch.helpers.bulk(es, es_data_itr())
    es.indices.flush()

    # influxdb
    ctx.send_event('Restoring InfluxDB metrics')
    call(INFLUXDB_RESTORE_CMD.format(path.join(tempdir, INFLUXDB)), shell=True)

    # credentials
    ctx.send_event('Restoring credentials')
    archive_cred_path = path.join(tempdir, CRED_DIR)
    cred_path = path.join(config.file_server_root, CRED_DIR)

    # in case when this is not first restore action
    if path.exists(cred_path):
        shutil.rmtree(cred_path)

    makedirs(cred_path)

    update_actions = []
    for node_id in listdir(archive_cred_path):
        makedirs(path.join(cred_path, node_id))
        agent_key_path = path.join(cred_path, node_id, CRED_KEY_NAME)
        shutil.copy(path.join(archive_cred_path, node_id, CRED_KEY_NAME),
                    agent_key_path)

        update_action = {
            '_op_type': 'update',
            '_index': 'cloudify_storage',
            '_type': 'node',
            '_id': node_id,
            'doc': {
                'properties': {
                    'cloudify_agent': {
                        'key': agent_key_path
                    }
                }
            }
        }

        update_actions.append(update_action)

    elasticsearch.helpers.bulk(es, update_actions)

    # end


@system_wide_workflow
def restore(ctx, snapshot_id, config, **kwargs):
    mappings = {
        '3.3': restore_snapshot_format_3_3
    }

    config = DictToAttributes(config)
    tempdir = tempfile.mkdtemp('-snapshot-data')

    try:
        file_server_root = config.file_server_root
        snapshots_dir = path.join(
            file_server_root,
            config.file_server_uploaded_snapshots_folder
        )

        snapshot_path = path.join(snapshots_dir, snapshot_id, '{0}.zip'
                                  .format(snapshot_id))

        with zipfile.ZipFile(snapshot_path, 'r') as zipf:
            zipf.extractall(tempdir)

        with open(path.join(tempdir, VERSION_FILE), 'r') as f:
            from_version = f.read()

        if from_version not in mappings:
            raise RuntimeError('Manager is not able to restore snapshot'
                               ' of manager {0}'.format(from_version))

        ctx.send_event('Starting restoring snapshot of manager {0}'
                       .format(from_version))
        mappings[from_version](ctx, config, tempdir)
        ctx.send_event('Successfully restored snapshot of manager {0}'
                       .format(from_version))

    finally:
        shutil.rmtree(tempdir)

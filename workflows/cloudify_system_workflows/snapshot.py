import json
import tempfile
import time
import shutil
import zipfile

from os import (path, makedirs, remove)
from subprocess import call

import elasticsearch
import elasticsearch.helpers

from cloudify.decorators import system_wide_workflow

ELASTICSEARCH = 'es_data'
INFLUXDB = 'influxdb-data'
INFLUXDB_DUMP_CMD = ('curl -s -G "http://localhost:8086/db/cloudify/series'
                     '?u=root&p=root&chunked=true" --data-urlencode'
                     ' "q=select * from /.*/" > {0}')
INFLUXDB_RESTORE_CMD = ('cat {0} | while read -r line; do curl -X POST '
                        '-d "[${{line}}]" "http://localhost:8086/db/cloudify/'
                        'series?u=root&p=root" ;done')


class DictToAttributes(object):
    def __init__(self, dic):
        self.__dict__ = dic


def get_json_objects(f):
    start_point = 0
    active_brackets = 0
    c = f.read(1)
    while c:
        if c == '{':
            active_brackets += 1
        elif c == '}':
            active_brackets -= 1
            if active_brackets == 0:
                end_point = f.tell()
                f.seek(start_point)
                yield f.read(end_point - start_point)
                start_point = end_point

        c = f.read(1)


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

        if path.isfile(p1):
            shutil.copy(p1, p2)
        else:
            if path.exists(p2):
                shutil.rmtree(p2, ignore_errors=True)
            shutil.copytree(p1, p2)


def _create_es_client(config):
    return elasticsearch.Elasticsearch(hosts=[{'host': config.db_address,
                                               'port': config.db_port}])


def _delete_all_docs(es_client):
    for doc in elasticsearch.helpers.scan(es_client):
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
    event_scan = elasticsearch.helpers.scan(es, index='cloudify_events')

    with open(path.join(tempdir, ELASTICSEARCH), 'w') as f:
        for item in storage_scan:
            f.write(json.dumps(item) + '\n')
        #for item in event_scan:     Temporarily commented out ..
        #    f.write(json.dumps(item) + '\n')  .. for testing

    # influxdb
    influxdb_file = path.join(tempdir, INFLUXDB)
    influxdb_temp_file = influxdb_file + '.temp'
    call(INFLUXDB_DUMP_CMD.format(influxdb_temp_file), shell=True)
    with open(influxdb_temp_file, 'r') as f, open(influxdb_file, 'w') as g:
        for obj in get_json_objects(f):
            obj = obj.replace('  ', '') + '\n'
            g.write(obj)

    remove(influxdb_temp_file)

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


@system_wide_workflow
def restore(ctx, snapshot_id, config, **kwargs):
    config = DictToAttributes(config)
    tempdir = tempfile.mkdtemp('-snapshot-data')

    file_server_root = config.file_server_root
    snapshots_dir = path.join(
        file_server_root,
        config.file_server_uploaded_snapshots_folder
    )

    snapshot_path = path.join(snapshots_dir, snapshot_id, '{0}.zip'
                              .format(snapshot_id))

    with zipfile.ZipFile(snapshot_path, 'r') as zipf:
        zipf.extractall(tempdir)

    # files/dirs copy
    copy_data(tempdir, config, to_archive=False)

    # elasticsearch
    es = _create_es_client(config)

    this_exec = es.get(id=ctx.execution_id, index='cloudify_storage', doc_type='execution')

    ctx.send_event('Deleting all ElasticSearch data')
    elasticsearch.helpers.bulk(es, _delete_all_docs(es))
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

    ctx.send_event('Restoring InfluxDB metrics')
    call(INFLUXDB_RESTORE_CMD.format(path.join(tempdir, INFLUXDB)), shell=True)

    # end
    shutil.rmtree(tempdir)

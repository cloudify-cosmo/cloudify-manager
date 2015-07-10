import tempfile
import shutil
import time
import json
import zipfile

from os import (path, makedirs)

import elasticsearch

from manager_rest import config
from manager_rest import responses
from manager_rest.blueprints_manager import get_blueprints_manager

ELASTICSEARCH = 'es_data'

DATA_TO_COPY = [
    ('/opt/influxdb/shared/data', 'influxdb-data'),
    (config.instance().file_server_blueprints_folder, 'blueprints'),
    (config.instance().file_server_uploaded_blueprints_folder,
        'uploaded-blueprints')
]


def copy_data(archive_root, to_archive=True):
    for (p1, p2) in DATA_TO_COPY:
        if p1[0] != '/':
            p1 = path.join(config.instance().file_server_root, p1)
        if p2[0] != '/':
            p2 = path.join(archive_root, p2)
        if not to_archive:
            p1, p2 = p2, p1

        shutil.copy(p1, p2)


def create_snapshot(self, snapshot_id):

    tempdir = tempfile.mkdtemp('-snapshot-data')

    file_server_root = config.instance().file_server_root
    snapshots_dir = path.join(
        file_server_root,
        config.instance().file_server_uploaded_snapshots_folder
    )

    # files/dirs copy
    copy_data(tempdir)

    # elasticsearch
    es_host = config.instance().db_address
    es_port = config.instance().db_port
    es = elasticsearch.Elasticsearch(hosts=[{'host': es_host,
                                             'port': es_port}])
    storage_scan = elasticsearch.helpers.scan(es, index='cloudify_storage')
    event_scan = elasticsearch.helpers.scan(es, index='cloudify_events')

    with open(path.join(tempdir, ELASTICSEARCH), 'w') as f:
        for item in storage_scan:
            f.write(json.dumps(item) + '\n')
        for item in event_scan:
            f.write(json.dumps(item) + '\n')

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

    return responses.Snapshot(
        id=snapshot_id,
        created_at=created_at
    )


def restore_snapshot(self, snapshot_id):

    tempdir = tempfile.mkdtemp('-snapshot-data')

    file_server_root = config.instance().file_server_root
    snapshots_dir = path.join(
        file_server_root,
        config.instance().file_server_uploaded_snapshots_folder
    )

    snapshot_path = path.join(snapshots_dir, snapshot_id, '{0}.zip'
                              .format(snapshot_id))

    with zipfile.ZipFile(snapshot_path, 'r') as zipf:
        zipf.extractall(tempdir)

    # files/dirs copy
    copy_data(tempdir, to_archive=False)

    # elasticsearch
    es_host = config.instance().db_address
    es_port = config.instance().db_port
    es = elasticsearch.Elasticsearch(hosts=[{'host': es_host,
                                             'port': es_port}])

    # elasticsearch > delete all documents
    es.indices.delete(index='cloudify_events')
    es.indices.delete(index='cloudify_storage')
    es.indices.create(index='cloudify_events')
    es.indices.create(index='cloudify_storage')

    def es_data_itr():
        for line in open(ELASTICSEARCH, 'r'):
            yield json.loads(line)

    elasticsearch.helpers.bulk(es, es_data_itr())

    get_blueprints_manager().recreate_deployments_enviroments()

    shutil.rmtree(tempdir)

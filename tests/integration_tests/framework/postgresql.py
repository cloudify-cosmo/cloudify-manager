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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import yaml
import logging
from contextlib import closing

import pg8000
from sqlalchemy.engine import reflection
from sqlalchemy.schema import (MetaData,
                               Table,
                               DropTable,
                               ForeignKeyConstraint,
                               DropConstraint)

from cloudify.utils import setup_logger

from manager_rest.storage import db
from manager_rest.storage.models import ProviderContext
from manager_rest.flask_utils import (get_postgres_conf,
                                      setup_flask_app as _setup_flask_app)
from manager_rest.storage.storage_utils import \
    create_default_user_tenant_and_roles

from manager_rest.constants import CURRENT_TENANT_CONFIG, PROVIDER_CONTEXT_ID

from integration_tests.framework import utils
from integration_tests.framework.docl import read_file as read_manager_file
from integration_tests.tests.constants import PROVIDER_CONTEXT, PROVIDER_NAME

logger = setup_logger('postgresql', logging.INFO)
setup_logger('postgresql.trace', logging.INFO)


security_config = None


def setup_flask_app():
    global security_config
    if not security_config:
        conf_file_str = read_manager_file('/opt/manager/rest-security.conf')
        security_config = yaml.load(conf_file_str)

    manager_ip = utils.get_manager_ip()
    return _setup_flask_app(
        manager_ip=manager_ip,
        driver='pg8000',
        hash_salt=security_config['hash_salt'],
        secret_key=security_config['secret_key']
    )


def run_query(query, db_name=None):
    conf = get_postgres_conf()
    manager_ip = utils.get_manager_ip()

    db_name = db_name or conf.db_name
    with closing(pg8000.connect(database=db_name,
                                user=conf.username,
                                password=conf.password,
                                host=manager_ip)) as con:
        con.autocommit = True
        logger.info('Trying to execute SQL query: ' + query)
        with closing(con.cursor()) as cur:
            try:
                cur.execute(query)
                fetchall = cur.fetchall()
                status_message = 'ok'
            except Exception, e:
                fetchall = None
                status_message = str(e)
            return {'status': status_message, 'all': fetchall}


def reset_storage():
    logger.info('Resetting PostgreSQL DB')
    app = setup_flask_app()

    # Rebuild the DB
    _safe_drop_all()
    db.create_all()

    # Add default tenant, admin user and provider context
    _add_defaults(app)

    # Clear the connection
    close_session(app)


def close_session(app):
    db.session.remove()
    db.get_engine(app).dispose()


def _add_defaults(app):
    """Add default tenant, admin user and provider context to the DB
    """
    provider_context = ProviderContext(
        id=PROVIDER_CONTEXT_ID,
        name=PROVIDER_NAME,
        context=PROVIDER_CONTEXT
    )
    db.session.add(provider_context)

    default_tenant = create_default_user_tenant_and_roles(
        admin_username=utils.get_manager_username(),
        admin_password=utils.get_manager_password(),
    )
    app.config[CURRENT_TENANT_CONFIG] = default_tenant


def _safe_drop_all():
    """Creates a single transaction that *always* drops all tables, regardless
    of relationships and foreign key constraints (as opposed to `db.drop_all`)
    """

    conn = db.engine.connect()

    # the transaction only applies if the DB supports
    # transactional DDL, i.e. Postgresql, MS SQL Server
    trans = conn.begin()

    inspector = reflection.Inspector.from_engine(db.engine)

    # gather all data first before dropping anything.
    # some DBs lock after things have been dropped in
    # a transaction.
    metadata = MetaData()

    tbs = []
    all_fks = []

    for table_name in inspector.get_table_names():
        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(ForeignKeyConstraint((), (), name=fk['name']))
        t = Table(table_name, metadata, *fks)
        tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(DropConstraint(fkc))

    for table in tbs:
        conn.execute(DropTable(table))

    trans.commit()

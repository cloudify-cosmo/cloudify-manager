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

import logging
from flask import Flask
from contextlib import closing

import pg8000

from cloudify.utils import setup_logger

from manager_rest.storage import db
from manager_rest.config import instance
from manager_rest.storage.models import Tenant
from manager_rest.security import user_datastore
from manager_rest.utils import add_users_and_roles_to_userstore
from manager_rest.test.security_utils import get_admin_user, get_admin_role

from integration_tests.framework import utils

logger = setup_logger('postgresql', logging.INFO)
setup_logger('postgresql.trace', logging.INFO)


app = None


def setup_app():
    global app
    if not app:
        conf = utils.get_postgres_client_details()
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = \
            'postgresql+pg8000://{0}:{1}@{2}/{3}'.format(
                conf.username,
                conf.password,
                conf.host,
                conf.db_name
            )
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Setup the mock app with the DB
    db.init_app(app)
    app.app_context().push()


def run_query(query, db_name=None):
    conf = utils.get_postgres_client_details()
    db_name = db_name or conf.db_name
    with closing(pg8000.connect(database=db_name,
                                user=conf.username,
                                password=conf.password,
                                host=conf.host)) as con:
        con.autocommit = True
        with closing(con.cursor()) as cur:
            try:
                cur.execute(query)
                logger.info('Running: ' + cur.query)
                status_message = cur.statusmessage
                fetchall = cur.fetchall()
            except Exception, e:
                fetchall = None
                status_message = str(e)
            return {'status': status_message, 'all': fetchall}


def reset_data():
    logger.info('Resetting PostgreSQL DB')

    setup_app()

    # Rebuild the DB
    db.drop_all()
    db.create_all()

    add_users_and_roles_to_userstore(
        user_datastore,
        get_admin_user(),
        get_admin_role()
    )

    t = Tenant(name=instance.default_tenant_name)
    db.session.add(t)
    db.session.commit()

    # Clear the connection
    db.session.remove()
    db.get_engine(app).dispose()

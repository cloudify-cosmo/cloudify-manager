from __future__ import with_statement

import contextlib
import logging
import os

from flask import current_app
from alembic import context
from sqlalchemy import engine_from_config, pool

from manager_rest import config as manager_config
from manager_rest.flask_utils import setup_flask_app

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
logger = logging.getLogger('alembic.env')


@contextlib.contextmanager
def default_config_path():
    """Set a default config path, and restore afterwards.

    We must avoid leaking out the default path, because unittests
    run this in-process, and that would taint them.
    """
    original_env = os.environ.get('MANAGER_REST_CONFIG_PATH')
    if not original_env and os.path.exists('/opt/manager/cloudify-rest.conf'):
        os.environ['MANAGER_REST_CONFIG_PATH'] = \
            '/opt/manager/cloudify-rest.conf'
    try:
        yield
    finally:
        os.environ.pop('MANAGER_REST_CONFIG_PATH', None)
        if original_env:
            os.environ['MANAGER_REST_CONFIG_PATH'] = original_env


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(dialect_name='postgresql')

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    config.set_main_option('sqlalchemy.url',
                           current_app.config.get('SQLALCHEMY_DATABASE_URI'))
    target_metadata = current_app.extensions['migrate'].db.metadata

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.readthedocs.org/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    engine = engine_from_config(config.get_section(config.config_ini_section),
                                prefix='sqlalchemy.',
                                poolclass=pool.NullPool)

    connection = engine.connect()
    context.configure(connection=connection,
                      target_metadata=target_metadata,
                      process_revision_directives=process_revision_directives,
                      **current_app.extensions['migrate'].configure_args)

    try:
        with context.begin_transaction():
            context.run_migrations()
    finally:
        connection.close()


if context.is_offline_mode():
    run_migrations_offline()
else:

    with default_config_path():
        if os.environ.get('MANAGER_REST_CONFIG_PATH'):
            manager_config.instance.load_configuration(from_db=False)
            app = setup_flask_app()
            app.app_context().push()

        run_migrations_online()

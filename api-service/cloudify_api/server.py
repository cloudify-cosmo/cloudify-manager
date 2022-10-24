import ssl
import logging

from fastapi import FastAPI

from manager_rest import config

from cloudify_api.config import Settings
from cloudify_api.listener import Listener
from cloudify_api.log import setup_logger
from cloudify_api import db

# THIS IS A HACK
# asyncpg's connect doesn't play nice with sqlalchemy's url parsing.
# This defines a wrapper around it that fixes up the kwargs to a form
# that will allow connecting with ssl client certs & CA cert verification
# This can be removed once sqlalchemy fixes its asyncpg driver
import asyncpg

original_connect = asyncpg.connect


def _hack_asyncpg_ssl_connect(*a, **kw):
    """Call asyncpg.connect in a way that allows using client & CA certs.

    SQLAlchemy parses the whole db url, and passes here just kwargs, like
    kw={'host': 'example.com', 'sslcert': '/cert.pem'} etc.
    This isn't compatible with asyncpg, because asyncpg can accept sslcert,
    sslkey, sslrootcert and sslcrl as part of the db url, but not as separate
    kwargs. When passing separate kwargs, like sqlalchemy does, it must be
    just a "ssl" argument, that is the ssl context, with all the certs
    already loaded into it.
    """
    if 'sslmode' in kw:
        sslmode = kw.pop('sslmode')
        if sslmode != 'disable':
            if 'sslrootcert' in kw:
                sslrootcert = kw.pop('sslrootcert')
                sslctx = ssl.create_default_context(
                    ssl.Purpose.SERVER_AUTH, cafile=sslrootcert)
                sslctx.check_hostname = True
            if 'sslcert' in kw:
                sslcert = kw.pop('sslcert')
                sslkey = kw.pop('sslkey')
                sslctx.load_cert_chain(sslcert, sslkey)
        else:
            sslctx = False
        kw['ssl'] = sslctx
    return original_connect(*a, **kw)


asyncpg.connect = _hack_asyncpg_ssl_connect


def get_settings():
    return Settings()


class CloudifyAPI(FastAPI):
    listener: Listener
    logger: logging.Logger
    settings: Settings

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = get_settings()
        self.logger = logging.getLogger('cloudify_api')
        config.instance.logger = self.logger

    def __str__(self):
        return f"{self.title}-{self.version}"

    def configure(self):
        config.instance.load_configuration()
        self.logger = setup_logger(
            config.instance.api_service_log_path,
            config.instance.api_service_log_level,
            config.instance.warnings)
        self._setup_sqlalchemy()
        self._setup_asyncpg_listener()

    def _setup_sqlalchemy(self):
        self._update_database_dsn()
        self.settings.sqlalchemy_engine_options = {
            'pool_size': 1,
        }
        self.db_session_maker = db.session_maker(
            db.engine(self.settings.sqlalchemy_dsn,
                      self.settings.sqlalchemy_engine_options))

    def _update_database_dsn(self):
        current = self.settings.sqlalchemy_dsn
        self.settings.sqlalchemy_dsn = config.instance.sqlalchemy_async_dsn
        self.settings.asyncpg_dsn = config.instance.asyncpg_dsn
        if current != self.settings.sqlalchemy_dsn:
            new_host = self.settings.sqlalchemy_dsn \
                .split('@')[1] \
                .split('/')[0]
            if current:
                self.logger.warning('DB leader changed: %s', new_host)
            else:
                self.logger.info('DB leader set to %s', new_host)

    def _setup_asyncpg_listener(self):
        if not self.settings.asyncpg_dsn:
            self._update_database_dsn()
        self.listener = Listener(self.settings.asyncpg_dsn, self.logger)

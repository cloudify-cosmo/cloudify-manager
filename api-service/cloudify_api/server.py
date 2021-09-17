import logging

from fastapi import FastAPI

from manager_rest import config

from cloudify_api.config import Settings
from cloudify_api.listener import Listener
from cloudify_api.log import setup_logger
from cloudify_api import db


def get_settings():
    return Settings()


class CloudifyAPI(FastAPI):
    def __init__(
            self,
            *args,
            **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = get_settings()
        self.logger = logging.getLogger('cloudify_api')

    def configure(self):
        if config.instance.postgresql_host is None:
            config.instance.load_from_file(
                self.settings.cloudify_rest_config_file)
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
        self.listener.listen_on_channel('audit_log_inserted')

from fastapi import FastAPI

from manager_rest import config

from manager_service.config import Settings
from manager_service.log import setup_logger
from manager_service.storage import db_engine, db_session_maker


def get_settings():
    return Settings()


class CloudifyManagerService(FastAPI):
    def __init__(
            self,
            *,
            load_config: bool = True,
            title: str = "Cloudify Manager Service",
            version: str = "6.2.0.dev1",
            **kwargs):
        super().__init__(
            title=title,
            version=version,
            **kwargs)

        self.settings = get_settings()
        if config.instance.postgresql_host is None:
            config.instance.load_from_file(
                self.settings.cloudify_rest_config_file)
        if load_config:
            config.instance.load_configuration()
        else:
            config.instance.can_load_from_db = False

        self.logger = setup_logger(
            config.instance.manager_service_log_path,
            config.instance.manager_service_log_level,
            config.instance.warnings)

        self._setup_sqlalchemy()

    def _setup_sqlalchemy(self):
        self.settings.sqlalchemy_engine_options = {
            'pool_size': 1,
        }
        self._update_database_dsn()
        self.db_session_maker = db_session_maker(
            db_engine(self.settings.sqlalchemy_database_dsn,
                      self.settings.sqlalchemy_engine_options))

    def _update_database_dsn(self):
        current = self.settings.sqlalchemy_database_dsn
        self.settings.sqlalchemy_database_dsn = config.instance.db_url
        if current != self.settings.sqlalchemy_database_dsn:
            new_host = self.settings.sqlalchemy_database_dsn \
                .split('@')[1] \
                .split('/')[0]
            if current:
                self.logger.warning('DB leader changed: %s', new_host)
            else:
                self.logger.info('DB leader set to %s', new_host)

    def db_session(self):
        session = self.db_session_maker()
        try:
            yield session
        finally:
            session.close()

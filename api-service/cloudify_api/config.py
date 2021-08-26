from pydantic import BaseSettings


class Settings(BaseSettings):
    cloudify_rest_config_file: str = '/opt/manager/cloudify-rest.conf'
    sqlalchemy_database_dsn: str = ''
    sqlalchemy_engine_options: dict = {}


settings = Settings()

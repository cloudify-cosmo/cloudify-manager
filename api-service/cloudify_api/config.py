from pydantic import BaseSettings


class Settings(BaseSettings):
    cloudify_rest_config_file: str = '/opt/manager/cloudify-rest.conf'
    sqlalchemy_dsn: str = ''
    sqlalchemy_engine_options: dict = {}
    asyncpg_dsn: str = ''


settings = Settings()

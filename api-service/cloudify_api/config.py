from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    cloudify_rest_config_file: str = '/opt/manager/cloudify-rest.conf'
    sqlalchemy_dsn: Optional[str]
    sqlalchemy_engine_options: dict = {}
    asyncpg_dsn: Optional[str]


settings = Settings()

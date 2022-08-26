from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    sqlalchemy_dsn: Optional[str]
    sqlalchemy_engine_options: dict = {}
    asyncpg_dsn: Optional[str]


settings = Settings()

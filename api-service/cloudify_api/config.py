from pydantic import BaseSettings


class Settings(BaseSettings):
    sqlalchemy_dsn: str | None
    sqlalchemy_engine_options: dict = {}
    asyncpg_dsn: str | None


settings = Settings()

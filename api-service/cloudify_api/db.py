from typing import Dict

from sqlalchemy.ext.asyncio import (create_async_engine,
                                    AsyncEngine,
                                    AsyncSession)
from sqlalchemy.orm import sessionmaker


def engine(database_dsn: str, connect_args: Dict) -> AsyncEngine:
    return create_async_engine(database_dsn, **connect_args)


def session_maker(engine: AsyncEngine) -> sessionmaker:
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

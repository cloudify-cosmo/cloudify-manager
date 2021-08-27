from typing import Dict

from sqlalchemy.ext.asyncio import (create_async_engine,
                                    AsyncEngine,
                                    AsyncSession)
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker

from cloudify_api.models import Base


def db_engine(database_dsn: str, connect_args: Dict) -> AsyncEngine:
    return create_async_engine(database_dsn, **connect_args)


def db_session_maker(engine: AsyncEngine) -> sessionmaker:
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def db_list(
        session: AsyncSession,
        model: Base,
        offset: int = 0,
        size: int = 100):
    stmt = select(model).offset(offset).limit(size)
    result = await session.execute(stmt)
    return result.scalars().all()

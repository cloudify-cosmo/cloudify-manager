from typing import Dict

from sqlalchemy.ext.asyncio import (create_async_engine,
                                    AsyncEngine,
                                    AsyncSession)
from sqlalchemy.orm import sessionmaker

from manager_rest.storage.management_models import Tenant  # noqa
from manager_rest.storage.resource_models import AuditLog  # noqa


def engine(database_dsn: str, connect_args: Dict) -> AsyncEngine:
    return create_async_engine(database_dsn, **connect_args)


def session_maker(e: AsyncEngine) -> sessionmaker:
    return sessionmaker(e, class_=AsyncSession, expire_on_commit=False)

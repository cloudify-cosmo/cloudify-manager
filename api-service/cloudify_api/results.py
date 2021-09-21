from typing import Any, List

from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import Executable
from sqlalchemy.sql.selectable import Select

from cloudify_api.common import CommonParameters


class Pagination(BaseModel):
    offset: int
    size: int
    total: int


class Metadata(BaseModel):
    pagination: Pagination


class PaginatedBase(BaseModel):
    items: List[Any]
    metadata: Metadata


class Paginated(PaginatedBase):
    @classmethod
    async def paginated(cls,
                        session: AsyncSession,
                        query: Select,
                        params: CommonParameters):
        count = await session.execute(select(func.count()).select_from(query))
        total_result = count.scalars().one()
        if params.order_by:
            order_by = params.order_by.split(",")
            if params.desc:
                order_by = [desc(f) for f in order_by]
            query = query.order_by(*order_by)
        if params.offset:
            query = query.offset(params.offset)
        if params.size:
            query = query.limit(params.size)
        result = await session.execute(query)
        return cls(items=result.scalars().all(),
                   metadata=Metadata(
                       pagination=Pagination(
                           offset=params.offset or 0,
                           size=params.size or total_result,
                           total=total_result)
                   ))


class DeletedResultBase(BaseModel):
    """Model describing execution result."""
    deleted: int


class DeletedResult(DeletedResultBase):
    @classmethod
    async def executed(cls,
                       session: AsyncSession,
                       stmt: Executable) -> DeletedResultBase:
        result = await session.execute(stmt)
        await session.commit()
        return cls(deleted=result.rowcount)

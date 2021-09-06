from typing import Any, Dict, List, Union

from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select


class Pagination(BaseModel):
    offset: int
    size: int
    total: int


class Metadata(BaseModel):
    pagination: Pagination


class Paginated(BaseModel):
    items: List[Any]
    metadata: Metadata

    @classmethod
    async def paginated(
                cls,
                session: AsyncSession,
                query: Select,
                params: Dict[str, Union[None, str, int]],
            ) -> BaseModel:
        count = await session.execute(select(func.count()).select_from(query))
        total_result = count.scalars().one()
        if params["order_by"] and isinstance(params["order_by"], str):
            order_by = params["order_by"].split(",")
            if params["desc"]:
                order_by = [desc(f) for f in order_by]
            query = query.order_by(*order_by)
        query = query.offset(params["offset"]).limit(params["size"])
        result = await session.execute(query)
        return cls(items=result.scalars().all(),
                   metadata=Metadata(
                       pagination=Pagination(
                           offset=params["offset"],
                           size=params["size"],
                           total=total_result)
                   ))

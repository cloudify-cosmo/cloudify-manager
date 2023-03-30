from fastapi import Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from cloudify_api import CloudifyAPI


def get_app(request: Request) -> CloudifyAPI:
    return request.app


async def make_db_session(request: Request) -> AsyncSession:
    async with request.app.db_session_maker() as session:
        yield session


class CommonParameters(BaseModel):
    order_by: str | None = None
    desc: bool = False
    offset: int | None = 0
    size: int | None = 100


def common_parameters(order_by: str | None = None,
                      desc: bool = False,
                      offset: int = 0,
                      size: int = 100) -> CommonParameters:
    return CommonParameters(
        order_by=order_by,
        desc=desc,
        offset=offset,
        size=size,
    )

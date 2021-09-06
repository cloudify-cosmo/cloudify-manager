from typing import Optional, Dict, Union

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from cloudify_api import CloudifyAPI


def get_app(request: Request) -> CloudifyAPI:
    return request.app


async def make_db_session(request: Request) -> AsyncSession:
    async with request.app.db_session_maker() as session:
        yield session


async def common_parameters(
        q: Optional[str] = None,
        order_by: Optional[str] = None,
        desc: bool = False,
        offset: int = 0,
        size: int = 100) -> Dict[str, Union[None, str, int]]:
    return {
        "q": q,
        "order_by": order_by,
        "desc": desc,
        "offset": offset,
        "size": size
    }

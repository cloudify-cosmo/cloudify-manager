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
        offset: int = 0,
        size: int = 1000) -> Dict[str, Union[None, str, int]]:
    return {"q": q, "offset": offset, "size": size}

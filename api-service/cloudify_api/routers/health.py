from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Healthcheck"])


@router.get("")
async def healthcheck():
    """Just a basic healthcheck endpoint"""
    return 'ok'

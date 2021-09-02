from typing import List

from fastapi import Depends, APIRouter
from sqlalchemy.future import select

from cloudify_api import models, schemas
from cloudify_api.common import common_parameters, get_app, make_db_session

router = APIRouter(prefix="/audit")


@router.get("",
            response_model=List[schemas.AuditLog],
            tags=["Audit Log"])
async def list_audit_log(
        session=Depends(make_db_session),
        app=Depends(get_app),
        params=Depends(common_parameters)
        ) -> List[schemas.AuditLog]:
    offset, size = params["offset"], params["size"]
    app.logger.debug("list_audit_log, offset=%d, size=%d", offset, size)
    result = await session.execute(
        select(models.AuditLog)
        .offset(offset)
        .limit(size)
    )
    return result.scalars().all()

from typing import List, Optional

from fastapi import Depends, APIRouter
from pydantic import BaseModel
from sqlalchemy.future import select

from cloudify_api import models
from cloudify_api.common import common_parameters, get_app, make_db_session
from cloudify_api.pagination import Paginated


class AuditLog(BaseModel):
    _storage_id: int
    ref_table: str
    ref_id: int
    operation: str
    creator_name: Optional[str]
    execution_id: Optional[str]
    created_at: str

    class Config:
        orm_mode = True


class PaginatedAuditLog(Paginated):
    items: List[AuditLog]


router = APIRouter(prefix="/audit")


@router.get("",
            response_model=PaginatedAuditLog,
            tags=["Audit Log"])
async def list_audit_log(
            creator_name: str = '',
            execution_id: str = '',
            session=Depends(make_db_session),
            app=Depends(get_app),
            p=Depends(common_parameters)
        ):
    app.logger.debug("list_audit_log, creator_name=%s, execution_id=%s")
    stmt = select(models.AuditLog)
    if creator_name:
        stmt = stmt.where(models.AuditLog.creator_name == creator_name)
    if execution_id:
        stmt = stmt.where(models.AuditLog.execution_id == execution_id)
    return await PaginatedAuditLog.paginated(session, stmt, p)

from datetime import datetime
from typing import List, Optional

from fastapi import Depends, APIRouter
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.future import select

from cloudify_api import models
from cloudify_api.common import common_parameters, get_app, make_db_session
from cloudify_api.results import ExecutionResult, Paginated


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


class TruncateParams(BaseModel):
    """Parameters passed to /audit/truncate endpoint."""
    before: datetime
    creator_name: Optional[str]
    execution_id: Optional[str]


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
        ) -> PaginatedAuditLog:
    app.logger.debug("list_audit_log, creator_name=%s, execution_id=%s",
                     creator_name, execution_id)
    stmt = select(models.AuditLog)
    if creator_name:
        stmt = stmt.where(models.AuditLog.creator_name == creator_name)
    if execution_id:
        stmt = stmt.where(models.AuditLog.execution_id == execution_id)
    return await PaginatedAuditLog.paginated(session, stmt, p)


@router.post("/truncate",
             response_model=ExecutionResult,
             tags=["Audit Log"])
async def truncate_audit_log(
            p: TruncateParams,
            session=Depends(make_db_session),
            app=Depends(get_app),
        ):
    app.logger.debug("truncate_audit_log, params=(%s)", p)
    stmt = delete(models.AuditLog)\
        .where(models.AuditLog.created_at <= p.before)
    if p.creator_name:
        stmt = stmt.where(models.AuditLog.creator_name == p.creator_name)
    if p.execution_id:
        stmt = stmt.where(models.AuditLog.execution_id == p.execution_id)
    return await ExecutionResult.executed(session, stmt)

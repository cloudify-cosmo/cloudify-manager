import asyncio
from datetime import datetime
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, parse_obj_as
from sqlalchemy import delete
from sqlalchemy.future import select
from sqlalchemy.sql.selectable import Select

from cloudify_api import models
from cloudify_api.common import common_parameters, get_app, make_db_session
from cloudify_api.listener import NOTIFICATION_CHANNEL
from cloudify_api.results import DeletedResult, Paginated


class AuditLog(BaseModel):
    _storage_id: int
    id: int
    ref_table: str
    ref_id: int
    ref_identifier: Optional[dict]
    operation: str
    creator_name: Optional[str]
    execution_id: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
        json_encoders = {
            datetime:
                lambda v: v.isoformat(timespec='milliseconds').split('+')[0],
        }

    def matches(self,
                creator_name: Optional[str] = None,
                execution_id: Optional[str] = None,
                since: Optional[datetime] = None) -> bool:
        """Check if audit log entry matches given constraints"""
        if since and self.created_at < since:
            return False
        if creator_name and self.creator_name != creator_name:
            return False
        if execution_id and self.execution_id != execution_id:
            return False
        return True


class InsertLog(BaseModel):
    ref_table: str
    ref_id: int
    ref_identifier: Optional[dict]
    operation: str
    creator_name: Optional[str]
    execution_id: Optional[str]
    created_at: datetime


class PaginatedAuditLog(Paginated):
    items: List[AuditLog]

    class Config:
        json_encoders = {
            datetime:
                lambda v: v.isoformat(timespec='milliseconds').split('+')[0],
        }


class TruncateParams(BaseModel):
    """Parameters passed to DELETE /audit endpoint."""
    before: datetime
    creator_name: Optional[str]
    execution_id: Optional[str]


router = APIRouter(prefix="/audit", tags=["Audit Log"])


@router.post("", status_code=204)
async def inject_audit_logs(logs: List[InsertLog],
                            session=Depends(make_db_session),
                            app=Depends(get_app)):
    app.logger.debug("insert_audit_logs with %s records",
                     len(logs))
    logs = [log.dict() for log in logs]
    await session.execute(
        models.AuditLog.__table__.insert(),
        logs,
    )
    await session.commit()


@router.get("", response_model=PaginatedAuditLog)
async def list_audit_log(creator_name: Optional[str] = None,
                         execution_id: Optional[str] = None,
                         since: Optional[datetime] = None,
                         session=Depends(make_db_session),
                         app=Depends(get_app),
                         p=Depends(common_parameters)) -> PaginatedAuditLog:
    app.logger.debug("list_audit_log, creator_name=%s, "
                     "execution_id=%s, since=%s",
                     creator_name, execution_id, since)
    query = select_audit_log_query(creator_name, execution_id, since)
    return await PaginatedAuditLog.paginated(session, query, p)


@router.get("/stream")
async def stream_audit_log(request: Request,
                           creator_name: Optional[str] = None,
                           execution_id: Optional[str] = None,
                           since: Optional[datetime] = None
                           ) -> StreamingResponse:
    request.app.logger.debug("Handling stream_audit_log request")
    queue = asyncio.Queue()
    request.app.listener.attach_queue(NOTIFICATION_CHANNEL, queue)
    headers = {"Content-Type": "text/event-stream"}
    return StreamingResponse(
        audit_log_streamer(request, queue, creator_name, execution_id, since),
        headers=headers)


@router.delete("", response_model=DeletedResult)
async def truncate_audit_log(p=Depends(TruncateParams),
                             session=Depends(make_db_session),
                             app=Depends(get_app)):
    app.logger.debug("truncate_audit_log, params=(%s)", p)
    stmt = delete(models.AuditLog)\
        .where(models.AuditLog.created_at <= p.before)
    if p.creator_name:
        stmt = stmt.where(models.AuditLog.creator_name == p.creator_name)
    if p.execution_id:
        stmt = stmt.where(models.AuditLog.execution_id == p.execution_id)
    return await DeletedResult.executed(session, stmt)


def select_audit_log_query(creator_name: Optional[str] = None,
                           execution_id: Optional[str] = None,
                           since: Optional[datetime] = None) -> Select:
    stmt = select(models.AuditLog).order_by('created_at')
    if creator_name is not None:
        stmt = stmt.where(models.AuditLog.creator_name == creator_name)
    if execution_id is not None:
        stmt = stmt.where(models.AuditLog.execution_id == execution_id)
    if since is not None:
        stmt = stmt.where(models.AuditLog.created_at >= since)
    return stmt


async def audit_log_streamer(request: Request,
                             queue: asyncio.Queue,
                             creator_name: Optional[str] = None,
                             execution_id: Optional[str] = None,
                             since: Optional[datetime] = None
                             ) -> Sequence[bytes]:
    streamed_ids = set()
    if since is not None:
        query = select_audit_log_query(creator_name=creator_name,
                                       execution_id=execution_id,
                                       since=since)
        async with request.app.db_session_maker() as session:
            db_records = await session.execute(query)
        for db_record in db_records.scalars().all():
            record = AuditLog.from_orm(db_record)
            yield make_streaming_response(record.json())
            streamed_ids.add(record.id)
    while True:
        try:
            data = await queue.get()
        except asyncio.CancelledError:
            request.app.listener.remove_queue(NOTIFICATION_CHANNEL, queue)
            break
        data.update({'id': data['_storage_id']})
        record: AuditLog = parse_obj_as(AuditLog, data)
        if not record.matches(creator_name, execution_id, since):
            continue
        yield make_streaming_response(record.json())
        if not queue.empty():
            streamed_ids.add(record.id)
        else:
            # At this point we can be sure, that the new streamed records do
            # not duplicate records retrieved in the previous loop
            streamed_ids.clear()


def make_streaming_response(data: str) -> bytes:
    return f"{data}\n\n".encode('utf-8', errors='ignore')

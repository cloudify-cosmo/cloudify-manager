import asyncio
from datetime import datetime
from typing import Sequence

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import parse_obj_as
from sqlalchemy import delete, select

from cloudify_api import db, CloudifyAPI
from cloudify_api.common import common_parameters, get_app, make_db_session
from cloudify_api.listener import NOTIFICATION_CHANNEL
from cloudify_api.models import (AuditLog,
                                 DeletedResult,
                                 InsertLog,
                                 PaginatedAuditLog,
                                 SelectParams)

router = APIRouter(prefix="/audit", tags=["Audit Log"])


def select_params(creator_name: str | None = None,
                  execution_id: str | None = None,
                  since: datetime | None = None,
                  before: datetime | None = None) -> SelectParams:
    params = {
        'creator_name': creator_name,
        'execution_id': execution_id,
        'since': since,
        'before': before,
    }
    return SelectParams.parse_obj(params)


@router.post("", status_code=204)
async def inject_audit_logs(logs: list[InsertLog],
                            session=Depends(make_db_session),
                            app=Depends(get_app)):
    app.logger.debug("insert_audit_logs with %s records",
                     len(logs))
    logs = [log.dict() for log in logs]
    await session.execute(
        db.AuditLog.__table__.insert(),
        logs,
    )
    await session.commit()


@router.get("", response_model=PaginatedAuditLog)
async def list_audit_log(session=Depends(make_db_session),
                         app=Depends(get_app),
                         params=Depends(select_params),
                         p=Depends(common_parameters)) -> PaginatedAuditLog:
    app.logger.debug("Handling list_audit_log request, params=%s", params)
    query = select(db.AuditLog)\
        .order_by('created_at')\
        .where(*params.as_filters())
    return await PaginatedAuditLog.paginated(session, query, p)


@router.get("/stream")
async def stream_audit_log(
        app=Depends(get_app),
        params=Depends(select_params),
) -> StreamingResponse:
    app.logger.debug("Handling stream_audit_log request, params=%s", params)
    queue = asyncio.Queue()
    app.listener.attach_queue(NOTIFICATION_CHANNEL, queue)
    headers = {"Content-Type": "text/event-stream"}
    return StreamingResponse(
        audit_log_streamer(app, params, queue),
        headers=headers)


@router.delete("", response_model=DeletedResult)
async def truncate_audit_log(
        app=Depends(get_app),
        session=Depends(make_db_session),
        params=Depends(select_params),
):
    app.logger.debug("Handling truncate_audit_log request, params=%s", params)
    if params.before is None:
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Mandatory parameter not provided: `before`"
        )
    stmt = delete(db.AuditLog).where(*params.as_filters())
    return await DeletedResult.executed(session, stmt)


async def audit_log_streamer(app: CloudifyAPI,
                             params: SelectParams,
                             queue: asyncio.Queue,
                             ) -> Sequence[bytes]:
    streamed_ids = set()

    if params.since is not None:
        query = select(db.AuditLog)\
            .order_by('created_at')\
            .where(*params.as_filters())
        async with app.db_session_maker() as session:
            db_records = await session.execute(query)
        for db_record in db_records.scalars().all():
            record = AuditLog.from_orm(db_record)
            yield make_streaming_response(record.json(exclude_none=True))
            streamed_ids.add(record.id)
    while True:
        try:
            data = await queue.get()
        except asyncio.CancelledError:
            app.listener.remove_queue(NOTIFICATION_CHANNEL, queue)
            break
        record: AuditLog = parse_obj_as(AuditLog, data)
        if not record.matches(params):
            continue
        await record.update_ref_identifier_tenant_name(
                app.get_tenant_name)

        yield make_streaming_response(record.json(exclude_none=True))
        if not queue.empty():
            streamed_ids.add(record.id)
        else:
            # At this point we can be sure, that the new streamed records do
            # not duplicate records retrieved in the previous loop
            streamed_ids.clear()


def make_streaming_response(data: str) -> bytes:
    return f"{data}\n\n".encode('utf-8', errors='ignore')

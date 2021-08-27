from typing import List

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from cloudify_api import models, schemas, server
from cloudify_api.storage import db_list


app = server.CloudifyAPI()


@app.get("/audit",
         response_model=List[schemas.AuditLog],
         tags=["Audit Log"])
async def list_audit_log(
        size: int = 100,
        offset: int = 0,
        session: AsyncSession = Depends(app.db_session)
        ) -> List[schemas.AuditLog]:
    app.logger.debug("list_audit_log, offset=%d, size=%d", offset, size)
    db_audit_logs = await db_list(session, models.AuditLog, offset, size)
    return db_audit_logs

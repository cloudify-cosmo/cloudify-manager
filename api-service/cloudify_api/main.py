from typing import List

from fastapi import Depends
from sqlalchemy.orm import Session

from cloudify_api import models, schemas, server
from cloudify_api.storage import db_list


app = server.CloudifyAPI()


@app.get("/audit",
         response_model=List[schemas.AuditLog],
         tags=["Audit Log"])
async def list_audit_log(
        size: int = 100,
        offset: int = 0,
        db: Session = Depends(app.db_session)) -> List[schemas.AuditLog]:
    app.logger.debug(f"list_audit_log, offset={offset}, size={size}")
    db_audit_logs = db_list(db, models.AuditLog, offset, size)
    return db_audit_logs

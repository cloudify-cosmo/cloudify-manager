from typing import List

from fastapi import Depends
from sqlalchemy.orm import Session

from manager_service import models, schemas, server
from manager_service.storage import db_list


manager = server.CloudifyManagerService()


@manager.get("/audit",
             response_model=List[schemas.AuditLog],
             tags=["Audit Log"])
async def list_audit_log(
        size: int = 100,
        offset: int = 0,
        db: Session = Depends(manager.db_session)) -> List[schemas.AuditLog]:
    manager.logger.debug(f"list_audit_log, offset={offset}, size={size}")
    db_audit_logs = db_list(db, models.AuditLog, offset, size)
    return db_audit_logs

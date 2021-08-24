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
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(manager.db_session)) -> List[schemas.AuditLog]:
    manager.logger.info(f"list_audit_log, skip={skip}, limit={limit}")
    db_audit_logs = db_list(db, models.AuditLog, skip=skip, limit=limit)
    return db_audit_logs

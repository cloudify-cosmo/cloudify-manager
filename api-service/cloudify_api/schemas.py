from typing import Optional

from pydantic import BaseModel


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

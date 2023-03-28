from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, root_validator
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import BinaryExpression
from sqlalchemy.sql.expression import Executable
from sqlalchemy.sql.selectable import Select

from cloudify_api import db
from cloudify_api.common import CommonParameters


class Pagination(BaseModel):
    offset: int
    size: int
    total: int


class Metadata(BaseModel):
    pagination: Pagination


class PaginatedBase(BaseModel):
    items: list[Any]
    metadata: Metadata


class Paginated(PaginatedBase):
    @classmethod
    async def paginated(cls,
                        session: AsyncSession,
                        query: Select,
                        params: CommonParameters):
        count = await session.execute(select(func.count()).select_from(query))
        total_result = count.scalars().one()
        if params.order_by:
            order_by = params.order_by.split(",")
            if params.desc:
                order_by = [desc(f) for f in order_by]
            query = query.order_by(*order_by)
        if params.offset:
            query = query.offset(params.offset)
        if params.size:
            query = query.limit(params.size)
        result = await session.execute(query)
        return cls(items=result.scalars().all(),
                   metadata=Metadata(
                       pagination=Pagination(
                           offset=params.offset or 0,
                           size=params.size or total_result,
                           total=total_result)
                   ))


class DeletedResultBase(BaseModel):
    """Model describing execution result."""
    deleted: int


class DeletedResult(DeletedResultBase):
    @classmethod
    async def executed(cls,
                       session: AsyncSession,
                       stmt: Executable) -> DeletedResultBase:
        result = await session.execute(stmt)
        await session.commit()
        return cls(deleted=result.rowcount)


class SelectParams(BaseModel):
    """Parameters passed to GET and DELETE /audit requests."""
    before: datetime | None  # required for DELETE
    since: datetime | None
    creator_name: str | None
    execution_id: str | None

    def as_filters(self) -> list[BinaryExpression]:
        filters = []
        if self.creator_name is not None:
            filters.append(db.AuditLog.creator_name == self.creator_name)
        if self.execution_id is not None:
            filters.append(db.AuditLog.execution_id == self.execution_id)
        if self.since is not None:
            filters.append(db.AuditLog.created_at >= self.since)
        if self.before is not None:
            filters.append(db.AuditLog.created_at <= self.before)
        return filters

    @root_validator
    def validator(cls, values):
        since, before = values.get('since'), values.get('before')
        if since is not None and before is not None:
            raise ValueError('Both parameters cannot be used: `since` and '
                             '`before`')
        return values


class Tenant(BaseModel):
    id: int
    name: str | None

    class Config:
        orm_mode = True


class RefIdentifier(BaseModel):
    tenant_id: int | None = Field(default=None, alias='_tenant_id')
    id: str | None
    storage_id: int | None = Field(default=None, alias='_storage_id')
    name: str | None
    manager_id: str | None
    username: str | None
    tenant_name: str | None

    class Config:
        allow_population_by_field_name = True
        extra = 'forbid'

    def dict(self, *args, **kwargs):
        kwargs.setdefault('exclude_none', True)
        return super().dict(*args, **kwargs)


class AuditLog(BaseModel):
    id: int | None = Field(default=None, alias='_storage_id')
    ref_table: str
    ref_id: int
    ref_identifier: RefIdentifier | None
    operation: str
    creator_name: str | None
    execution_id: str | None
    created_at: datetime
    tenant: Tenant | None

    class Config:
        allow_population_by_field_name = True
        extra = 'forbid'
        orm_mode = True
        json_encoders = {
            datetime:
                lambda v: v.isoformat(timespec='milliseconds').split('+')[0],
        }

    @root_validator
    def validator(cls, values):
        if values.get('tenant') and values.get('ref_identifier'):
            tenant: Tenant = values['tenant']
            values['ref_identifier'].tenant_name = tenant.name
        return values

    def dict(self, *args, **kwargs):
        kwargs['exclude'] = {'tenant': True}
        return super().dict(*args, **kwargs)

    def matches(self, params: SelectParams) -> bool:
        """Check if audit log entry matches given constraints"""
        if params.since and self.created_at < params.since:
            return False
        if params.creator_name and self.creator_name != params.creator_name:
            return False
        if params.execution_id and self.execution_id != params.execution_id:
            return False
        return True

    async def update_ref_identifier_tenant_name(self, async_getter):
        if self.ref_identifier and self.ref_identifier.tenant_id is not None:
            tenant_id = self.ref_identifier.tenant_id
            tenant_name = await async_getter(tenant_id)
            if tenant_name is not None:
                self.ref_identifier.tenant_name = tenant_name


class InsertLog(BaseModel):
    ref_table: str
    ref_id: int
    ref_identifier: RefIdentifier | None
    operation: str
    creator_name: str | None
    execution_id: str | None
    created_at: datetime


class PaginatedAuditLog(Paginated):
    items: list[AuditLog]

    class Config:
        json_encoders = {
            datetime:
                lambda v: v.isoformat(timespec='milliseconds').split('+')[0],
        }

    def dict(self, *args, **kwargs):
        kwargs['exclude_none'] = True
        kwargs['by_alias'] = False
        return super().dict(*args, **kwargs)

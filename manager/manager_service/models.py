from sqlalchemy import MetaData
from sqlalchemy.ext.declarative import declarative_base

from manager_rest.storage.resource_models import AuditLog  # noqa


Base = declarative_base(metadata=MetaData(naming_convention={
    # This is to generate migration scripts with constraint names
    # using the same naming convention used by PostgreSQL by default
    # http://stackoverflow.com/a/4108266/183066
    'ix': '%(table_name)s_%(column_0_name)s_idx',
    'uq': '%(table_name)s_%(column_0_name)s_key',
    'ck': '%(table_name)s_%(column_0_name)s_check',
    'fk': '%(table_name)s_%(column_0_name)s_fkey',
    'pk': '%(table_name)s_pkey',
}))

from typing import Dict

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from sqlalchemy.orm import sessionmaker, Session

from manager_service.models import Base


def db_engine(
        database_dsn: str,
        connect_args: Dict) -> Engine:
    return create_engine(database_dsn, **connect_args)


def db_session_maker(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def db_list(db: Session, model: Base, skip: int = 0, limit: int = 100):
    return db.query(model).offset(skip).limit(limit).all()

import aria
from aria.storage.sql_mapi import SQLAlchemyModelAPI

from .models_base import db

_model_storage = None


def initiator():
    """Get SQLAlchemy engine and session to be used by aria.

    :return: SQLAlchemy engine and session
    :rtype: Dict[str]

    """
    assert db.engine is not None
    assert db.session is not None
    return {
        'engine': db.engine,
        'session': db.session,
    }


def model_storage():
    """Get aria model storage.

    The model storage can be used to interact with the database using the mapi
    abstraction.

    :return: Aria model storage
    :rtype: :class:`aria.storage.core.ModelStorage`

    """
    global _model_storage
    if _model_storage is None:
        _model_storage = aria.application_model_storage(
            api=SQLAlchemyModelAPI,
            initiator=initiator,
        )
    return _model_storage

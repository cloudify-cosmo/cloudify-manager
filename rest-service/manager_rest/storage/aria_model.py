import aria
from aria.storage.sql_mapi import SQLAlchemyModelAPI

from .models_base import db


def get_model_storage():
    """Get aria model storage.

    The model storage can be used to interact with the database using the mapi
    abstraction.

    :return: Aria model storage
    :rtype: :class:`aria.storage.core.ModelStorage`

    """
    return aria.application_model_storage(
        api=SQLAlchemyModelAPI,
        api_kwargs=dict(engine=db.engine, session=db.session),
        initiator=False,
        models_prefix='ARIA_'
    )

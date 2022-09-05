from typing import Optional
from pydantic import (
    BaseModel,
    NonNegativeInt,
    constr,
    Field,
    root_validator,
)

from .validation_types import (
    DateTime,
)


class Pagination(BaseModel):
    size: Optional[NonNegativeInt] = Field(
        alias='_size',
    )
    offset: Optional[NonNegativeInt] = Field(
        alias='_offset',
    )


class Range(BaseModel):
    key: str
    from_field: Optional[DateTime] = Field(
        alias='from',
    )
    to: Optional[DateTime]

    @root_validator
    def check_from_or_to(cls, values):
        if ('from_field' in values and values['from_field']) or ('to' in values and values['to']):
            return values

        raise ValueError('At least one of from/to must be passed')


class Sort(BaseModel):
    sort: constr(regex=r'[+-]?[\w@]+')

from typing import (
    Optional,
    List,
)
from pydantic import (
    BaseModel,
    NonNegativeInt,
    constr,
    Field,
    root_validator,
    validator,
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
    from_field: Optional[DateTime]
    to: Optional[DateTime]

    @root_validator(pre=True)
    def check_from_or_to(cls, values):
        if values.get('from_field') or values.get('to'):
            return values

        raise ValueError('At least one of from/to must be passed')


class RangesList(BaseModel):
    ranges: List[Range] = Field(
        alias='_range',
        default=[],
    )

    @validator('ranges', pre=True, each_item=True)
    def split_ranges(cls, v):
        parts = v.split(',')

        if len(parts) != 3:
            raise ValueError('range must contain exactly 3 fields')

        return Range(
            key=parts[0] or None,
            from_field=parts[1] or None,
            to=parts[2] or None,
        )


class Sort(BaseModel):
    sort: List[constr(regex=r'[+-]?@?\w+')] = Field(  # noqa
        alias='_sort',
        default=[],
    )

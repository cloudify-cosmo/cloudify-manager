import pytz

from datetime import datetime
from dateutil.parser import parse as parse_datetime
from typing import Optional
from pydantic import (
    BaseModel,
    PositiveInt,
    constr,
    Field,
    root_validator,
    validator,
)


class Pagination(BaseModel):
    size: Optional[PositiveInt] = Field(
        alias='_size',
    )
    offset: Optional[PositiveInt] = Field(
        alias='_offset',
    )


class Range(BaseModel):
    key: str
    from_field: Optional[datetime] = Field(
        alias='from',
    )
    to: Optional[datetime]

    @root_validator
    def check_from_or_to(cls, values):
        if ('from_field' in values and values['from_field']) or ('to' in values and values['to']):
            return values

        raise ValueError('At least one of from/to must be passed')

    @validator('from_field', 'to', pre=True)
    def valid_datetime(cls, datetime_str):
        """Make sure that datetime is parseable.

        :param datetime_str: Datetime value to parse
        :type datetime_str: str
        :return: The datetime value after parsing
        :rtype: :class:`datetime.datetime`

        """
        assert datetime_str is not None, '"from" and "to" may not be None'

        try:
            parsed_datetime = parse_datetime(datetime_str)
        except Exception:
            raise ValueError('Datetime parsing error')

        # Make sure timestamp is in UTC, but doesn't have any timezone info.
        # Passing timezone aware timestamp to PosgreSQL through SQLAlchemy
        # doesn't seem to work well in manual tests
        if parsed_datetime.tzinfo:
            parsed_datetime = (
                parsed_datetime.astimezone(pytz.timezone('UTC'))
                .replace(tzinfo=None)
            )

        return parsed_datetime


class Sort(BaseModel):
    sort: constr(regex=r'[+-]?[\w@]+')

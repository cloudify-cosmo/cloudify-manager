import pytz

from dateutil.parser import parse as parse_datetime
from datetime import datetime


class DateTime(datetime):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        if not isinstance(value, str):
            raise TypeError('string required')

        parsed_datetime = parse_datetime(value)

        if not parsed_datetime:
            raise ValueError('DateTime parsing error')

        if parsed_datetime.tzinfo:
            parsed_datetime = (
                parsed_datetime.astimezone(
                    pytz.timezone('UTC')
                )
                .replace(tzinfo=None)
            )
        return parsed_datetime

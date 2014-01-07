__author__ = 'dan'

import re


def _from_pattern(pattern, obj_type, *args):
    def coerce_value(value):
        value = str(value)
        match = pattern.search(value)
        if match is not None:
            return obj_type(match.group(1), *args)
        raise ValueError('unable to coerce "%s" into a %s' % (value, obj_type.__name__))
    return coerce_value

_to_hex = _from_pattern(re.compile('([-+]?[0-9A-F]+)', re.IGNORECASE), int, 16)


# TODO protect and validate chunked stream
def decode(input_stream, buffer_size=8192):
    while True:
        index = input_stream.readline()
        length = _to_hex(index)
        remaining = length
        while remaining > 0:
            if buffer_size >= remaining:
                result = input_stream.read(remaining)
                remaining = 0
            else:
                result = input_stream.read(buffer_size)
                remaining -= buffer_size
            yield result
        input_stream.read(2)
        if not length:
            # read last \r\n
            input_stream.read(2)
            return

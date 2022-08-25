"""Swagger stand-ins.

Version upgrades forced us to temporarily disable swagger docs, but no-op
functions keeping the same interface allow us to keep using it meanwhile.

RD-5683 is about finding an actual implementation for this module.
"""


def operation(**kwargs):
    def _deco(f):
        return f
    return _deco


def model(cls):
    return cls

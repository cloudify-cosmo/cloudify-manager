import typing

import flask
from flask import g
from manager_rest.storage.models_base import db


def set_audit_method(method: str):
    g.audit_auth_method = method


def set_username(username: str):
    g.audit_username = username
    db.session.execute("SET SESSION audit.username = :name",
                       params={'name': username})


def set_tenant(tenant: str):
    g.audit_tenant = tenant


def extend_headers(response: flask.Response) -> flask.Response:
    audit_headers = _prepare_headers()
    response.headers.extend(audit_headers)
    return response


def _prepare_headers() -> typing.List[typing.Tuple[str, str]]:
    headers = []
    if 'audit_auth_method' in g:
        headers.append(('X-Cloudify-Audit-Auth-Method', g.audit_auth_method))
    if 'audit_tenant' in g:
        headers.append(('X-Cloudify-Audit-Tenant', g.audit_tenant))
    if 'audit_username' in g:
        headers.append(('X-Cloudify-Audit-Username', g.audit_username))
    return headers

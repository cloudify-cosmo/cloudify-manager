import typing

import flask
from manager_rest.storage.models_base import db


def set_audit_method(method: typing.Optional[str]):
    flask.g.audit_auth_method = method


def set_username(username: str):
    flask.g.audit_username = username
    db.session.execute("SET SESSION audit.username = :name",
                       params={'name': username})


def reset():
    """Clean all session variables"""
    set_audit_method(None)
    db.session.execute("RESET audit.username")
    db.session.execute("RESET audit.execution_id")


def set_tenant(tenant: str):
    flask.g.audit_tenant = tenant


def extend_headers(response: flask.Response) -> flask.Response:
    audit_headers = _prepare_headers()
    response.headers.extend(audit_headers)
    return response


def _prepare_headers() -> typing.List[typing.Tuple[str, str]]:
    headers = []
    if 'audit_auth_method' in flask.g:
        headers.append(('X-Cloudify-Audit-Auth-Method',
                        flask.g.audit_auth_method))
    if 'audit_tenant' in flask.g:
        headers.append(('X-Cloudify-Audit-Tenant',
                        flask.g.audit_tenant))
    if 'audit_username' in flask.g:
        headers.append(('X-Cloudify-Audit-Username',
                        flask.g.audit_username))
    return headers

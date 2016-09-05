from flask import current_app

from dsl_parser import constants
from manager_rest.storage import storage_manager
from dsl_parser import utils as dsl_parser_utils


def get_parser_context(sm=None):
    sm = sm or storage_manager.get_storage_manager()
    if not hasattr(current_app, 'parser_context'):
        update_parser_context(sm.get_provider_context().context)
    return current_app.parser_context


def update_parser_context(context):
    raw_parser_context = _extract_parser_context(context)
    resolver = dsl_parser_utils.create_import_resolver(
            raw_parser_context['resolver_section'])
    validate_definitions_version = raw_parser_context[
        'validate_definitions_version']
    current_app.parser_context = {
        'resolver': resolver,
        'validate_version': validate_definitions_version
    }


def _extract_parser_context(context):
    context = context or {}
    cloudify_section = context.get(constants.CLOUDIFY, {})
    return {
        'resolver_section': cloudify_section.get(
                constants.IMPORT_RESOLVER_KEY),
        'validate_definitions_version': cloudify_section.get(
                constants.VALIDATE_DEFINITIONS_VERSION, True)
    }

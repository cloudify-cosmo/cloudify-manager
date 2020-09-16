#########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from flask import current_app

from dsl_parser import constants
from dsl_parser import utils as dsl_parser_utils

from manager_rest.storage import get_storage_manager
from manager_rest.constants import PROVIDER_CONTEXT_ID
from manager_rest.storage.models import ProviderContext


def get_parser_context(sm=None, resolver_parameters=None):
    sm = sm or get_storage_manager()
    if not hasattr(current_app, 'parser_context'):
        update_parser_context(
            sm.get(ProviderContext, PROVIDER_CONTEXT_ID).context,
            resolver_parameters
        )
    return current_app.parser_context


def update_parser_context(context, resolver_parameters=None):
    current_app.parser_context = _extract_parser_context(
        context, resolver_parameters)


def _extract_parser_context(context, resolver_parameters):
    context = context or {}
    cloudify_section = context.get(constants.CLOUDIFY, {})
    resolver_section = cloudify_section.get(
        constants.IMPORT_RESOLVER_KEY) or {}
    resolver_section.setdefault(
        'implementation',
        'manager_rest.'
        'resolver_with_catalog_support:ResolverWithCatalogSupport')
    if resolver_parameters:
        if constants.PARAMETERS not in resolver_section:
            resolver_section[constants.PARAMETERS] = {}
        resolver_section[constants.PARAMETERS].update(resolver_parameters)
    resolver = dsl_parser_utils.create_import_resolver(resolver_section)
    return {
        'resolver': resolver,
        'validate_version': cloudify_section.get(
            constants.VALIDATE_DEFINITIONS_VERSION, True)
    }

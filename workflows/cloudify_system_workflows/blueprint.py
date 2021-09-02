########
# Copyright (c) 2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import os
import shutil
import tempfile
import requests
import traceback

from setuptools import archive_util

from cloudify._compat import unquote
from cloudify.decorators import workflow
from cloudify.manager import get_rest_client
from cloudify.models_states import BlueprintUploadState
from cloudify.exceptions import InvalidBlueprintImport, WorkflowFailed
from cloudify.constants import (CONVENTION_APPLICATION_BLUEPRINT_FILE,
                                SUPPORTED_ARCHIVE_TYPES)

from dsl_parser import constants, tasks
from dsl_parser import utils as dsl_parser_utils
from dsl_parser.exceptions import DSLParsingException


@workflow
def upload(ctx, **kwargs):

    client = get_rest_client()

    # extract the execution parameters
    blueprint_id = kwargs['blueprint_id']
    app_file_name = kwargs['app_file_name']
    url = kwargs['url']
    file_server_root = kwargs['file_server_root']
    validate_only = kwargs['validate_only']
    labels = kwargs.get('labels')

    # Download the archive, one way or the other
    archive_target_path = tempfile.mkdtemp()
    try:
        if url:
            # download the blueprint archive from URL using requests:
            if not validate_only:
                client.blueprints.update(
                    blueprint_id,
                    update_dict={'state': BlueprintUploadState.UPLOADING})
            with requests.get(url, stream=True, timeout=(5, None)) as resp:
                resp.raise_for_status()
                archive_file_path = os.path.join(archive_target_path,
                                                 os.path.basename(url))
                with open(archive_file_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            # Upload the downloaded archive to the manager
            if not validate_only:
                client.blueprints.upload_archive(
                    blueprint_id,
                    archive_path=archive_file_path)

        else:
            # download the blueprint archive using REST
            archive_file_path = client.blueprints.download(
                blueprint_id, output_file=archive_target_path)
    except Exception as e:
        client.blueprints.update(
            blueprint_id,
            update_dict={'state': BlueprintUploadState.FAILED_UPLOADING,
                         'error': str(e),
                         'error_traceback': traceback.format_exc()})
        remove(archive_target_path)
        raise

    ctx.logger.info('Blueprint archive uploaded. Extracting...')

    # Extract the archive so we can parse it
    if not validate_only:
        client.blueprints.update(
            blueprint_id,
            update_dict={'state': BlueprintUploadState.EXTRACTING})
    try:
        archive_util.unpack_archive(archive_file_path, archive_target_path)
    except archive_util.UnrecognizedFormat:
        error_msg = 'Blueprint archive is of an unrecognized format. ' \
                    'Supported formats are: ' \
                    '{0}'.format(SUPPORTED_ARCHIVE_TYPES)
        handle_failed_extracting(ctx, client, blueprint_id, error_msg,
                                 archive_target_path)
    except Exception as e:
        handle_failed_extracting(ctx, client, blueprint_id, str(e),
                                 archive_target_path)
    archive_file_list = os.listdir(archive_target_path)
    # ignore the archive file for now
    archive_file_list.remove(os.path.basename(archive_file_path))
    # the other item in the archive dir is the extracted app, which is
    # supposed to consist of one folder in a properly-structured archive
    app_dir = os.path.join(archive_target_path, archive_file_list[0])
    if len(archive_file_list) != 1 or not os.path.isdir(app_dir):
        error_msg = 'Archive must contain exactly 1 directory'
        handle_failed_extracting(ctx, client, blueprint_id, error_msg,
                                 archive_target_path)

    # get actual app file name
    if app_file_name:
        app_file_name = unquote(app_file_name)
        application_file = os.path.join(app_dir, app_file_name)
        if not os.path.isfile(application_file):
            error_msg = '{0} does not exist in the application ' \
                        'directory'.format(app_file_name)
            handle_failed_extracting(ctx, client, blueprint_id, error_msg,
                                     archive_target_path)
    else:
        app_file_name = CONVENTION_APPLICATION_BLUEPRINT_FILE
        application_file = os.path.join(app_dir, app_file_name)
        if not os.path.isfile(application_file):
            error_msg = 'Application directory is missing blueprint.yaml and' \
                        ' application_file_name query parameter was not passed'
            handle_failed_extracting(ctx, client, blueprint_id, error_msg,
                                     archive_target_path)

    ctx.logger.info('Blueprint archive extracted. Parsing...')

    # Parse plan
    if not validate_only:
        client.blueprints.update(
            blueprint_id, update_dict={'state': BlueprintUploadState.PARSING})

    dsl_location = os.path.join(app_dir, app_file_name)

    provider_context = client.manager.get_context()['context']
    try:
        parser_context = extract_parser_context(
            provider_context,
            resolver_parameters={
                'file_server_root': file_server_root,
                'client': client
            })
    except dsl_parser_utils.ResolverInstantiationError as e:
        ctx.logger.critical(str(e))
        client.blueprints.update(
            blueprint_id,
            update_dict={'state': BlueprintUploadState.FAILED_PARSING,
                         'error': str(e),
                         'error_traceback': traceback.format_exc()})
        raise
    try:
        plan = tasks.parse_dsl(dsl_location,
                               file_server_root,
                               **parser_context)
    except (InvalidBlueprintImport, DSLParsingException) as e:
        error_msg = 'Invalid blueprint - {}'.format(e)
        ctx.logger.critical(error_msg)
        client.blueprints.update(
            blueprint_id,
            update_dict={'state': BlueprintUploadState.INVALID,
                         'error': error_msg,
                         'error_traceback': traceback.format_exc()})
        raise
    except Exception as e:
        error_msg = 'Failed parsing blueprint - {}'.format(e)
        ctx.logger.critical(error_msg)
        client.blueprints.update(
            blueprint_id,
            update_dict={'state': BlueprintUploadState.FAILED_PARSING,
                         'error': error_msg,
                         'error_traceback': traceback.format_exc()})
        raise
    finally:
        remove(archive_target_path)

    if validate_only:
        ctx.logger.info('Blueprint validated.')
    else:
        ctx.logger.info('Blueprint parsed. Updating DB with blueprint plan.')

    # Warn users re: using multiple rel's between the same source and target
    check_multiple_relationship_to_one_target(ctx, plan)

    # Update DB with parsed plan
    update_dict = {
        'plan': plan,
        'main_file_name': app_file_name,
        'state': BlueprintUploadState.UPLOADED,
    }
    if plan.get('description'):
        update_dict['description'] = plan['description']
    if labels:
        update_dict['labels'] = labels
    try:
        client.blueprints.update(blueprint_id, update_dict=update_dict)
    except Exception as e:
        error_msg = 'Failed uploading blueprint - {}'.format(e)
        client.blueprints.update(
            blueprint_id,
            update_dict={'state': BlueprintUploadState.FAILED_UPLOADING,
                         'error': error_msg,
                         'error_traceback': traceback.format_exc()})
        raise


def extract_parser_context(context, resolver_parameters):
    context = context or {}
    cloudify_section = context.get(constants.CLOUDIFY, {})
    resolver_section = cloudify_section.get(constants.IMPORT_RESOLVER_KEY, {})
    resolver_section.setdefault(
        'implementation',
        'cloudify_system_workflows.dsl_import_resolver'
        '.resolver_with_catalog_support:ResolverWithCatalogSupport')
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


def remove(path):
    if os.path.exists(path):
        if os.path.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path)


def handle_failed_extracting(ctx, client, blueprint_id, error_msg,
                             archive_path):
    ctx.logger.critical('Failed extracting. {}'.format(error_msg))
    client.blueprints.update(
        blueprint_id,
        update_dict={'state': BlueprintUploadState.FAILED_EXTRACTING,
                     'error': error_msg,
                     'error_traceback': traceback.format_exc()})
    remove(archive_path)
    raise WorkflowFailed(error_msg)


def check_multiple_relationship_to_one_target(ctx, plan):
    for node in plan['nodes']:
        rel_targets = [x['target_id'] for x in node['relationships']]
        if len(rel_targets) > len(set(rel_targets)):
            ctx.logger.warning(
                "Node '%s' contains multiple relationships with the same "
                "target. Only the last of these will have its interface "
                "operations executed.", node['name'])

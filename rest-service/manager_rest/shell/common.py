from os import environ
from os.path import exists, isfile, join
import typing

import yaml

from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    SUPPORTED_ARCHIVE_TYPES)
from manager_rest.flask_utils import (setup_flask_app, set_admin_current_user,
                                      get_tenant_by_name, set_tenant_in_app)
from manager_rest.storage import models
from manager_rest import config

DEFAULT_TENANT = 'default_tenant'
END_POS = 'end_pos'
MAX_IMPORT_TOKEN_LENGTH = 200
REST_HOME_DIR = '/opt/manager'
REST_CONFIG_PATH = join(REST_HOME_DIR, 'cloudify-rest.conf')
REST_SECURITY_CONFIG_PATH = join(REST_HOME_DIR, 'rest-security.conf')
START_POS = 'start_pos'


class UpdateException(Exception):
    pass


def setup_environment():
    for value, envvar in [
        (REST_CONFIG_PATH, 'MANAGER_REST_CONFIG_PATH'),
        (REST_SECURITY_CONFIG_PATH, 'MANAGER_REST_SECURITY_CONFIG_PATH'),
    ]:
        if value is not None:
            environ[envvar] = value

    app = setup_flask_app()
    with app.app_context():
        config.instance.load_configuration()
    set_admin_current_user(app)
    set_tenant_in_app(get_tenant_by_name(DEFAULT_TENANT))


def blueprint_file_name(blueprint: models.Blueprint) -> str:
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        blueprint.main_file_name
    )


def archive_file_name(blueprint: models.Blueprint) -> str:
    for arc_type in SUPPORTED_ARCHIVE_TYPES:
        # attempting to find the archive file on the file system
        local_path = join(
            config.instance.file_server_root,
            FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
            blueprint.tenant.name,
            blueprint.id,
            '{0}.{1}'.format(blueprint.id, arc_type))

        if isfile(local_path):
            archive_type = arc_type
            break
    else:
        raise UpdateException("Could not find blueprint's archive; "
                              "Blueprint ID: {0}".format(blueprint.id))
    return join(
        config.instance.file_server_root,
        FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        '{0}.{1}'.format(blueprint.id, archive_type)
    )


def blueprint_updated_file_name(blueprint: models.Blueprint) -> str:
    base_file_name = '.'.join(blueprint.main_file_name.split('.')[:-1])
    index = 0
    updated_file_name = '{0}-new.yaml'.format(base_file_name)
    while exists(join(config.instance.file_server_root,
                      FILE_SERVER_BLUEPRINTS_FOLDER,
                      blueprint.tenant.name,
                      blueprint.id,
                      updated_file_name)):
        updated_file_name = '{0}-{1:02d}.yaml'.format(base_file_name, index)
        index += 1
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        updated_file_name
    )


def blueprint_diff_file_name(blueprint: models.Blueprint) -> str:
    base_file_name = '.'.join(blueprint.main_file_name.split('.')[:-1])
    index = 0
    diff_file_name = '{0}.diff'.format(base_file_name)
    while exists(join(config.instance.file_server_root,
                      FILE_SERVER_BLUEPRINTS_FOLDER,
                      blueprint.tenant.name,
                      blueprint.id,
                      diff_file_name)):
        diff_file_name = '{0}-{1:02d}.diff'.format(base_file_name, index)
        index += 1
    return join(
        config.instance.file_server_root,
        FILE_SERVER_BLUEPRINTS_FOLDER,
        blueprint.tenant.name,
        blueprint.id,
        diff_file_name
    )


def get_imports_position(blueprint_file: typing.BinaryIO) -> tuple:
    level, start_pos, end_pos = 0, 0, 0
    imports_token = None
    blueprint_file.seek(0, 0)
    for t in yaml.scan(blueprint_file):
        if isinstance(t, (yaml.tokens.BlockMappingStartToken,
                          yaml.tokens.BlockSequenceStartToken,
                          yaml.tokens.FlowMappingStartToken,
                          yaml.tokens.FlowSequenceStartToken)):
            level += 1
        if isinstance(t, (yaml.tokens.BlockEndToken,
                          yaml.tokens.FlowMappingEndToken,
                          yaml.tokens.FlowSequenceEndToken)):
            level -= 1

        if isinstance(t, yaml.tokens.ScalarToken):
            if level == 1 and t.value == 'imports':
                imports_token = t
                start_pos = t.end_mark.index + 1
                continue

            token_length = t.end_mark.index - t.start_mark.index

            if (level >= 1
                    and imports_token
                    and token_length < MAX_IMPORT_TOKEN_LENGTH):
                if not start_pos:
                    start_pos = t.start_mark.index
                end_pos = t.end_mark.index

        if isinstance(t, yaml.tokens.KeyToken) and imports_token:
            break

    return start_pos, end_pos


def get_line_separator(blueprint_file: typing.BinaryIO) -> str:
    blueprint_file.seek(0, 0)
    blueprint_excerpt = blueprint_file.read(1000)
    if b'\r\n' in blueprint_excerpt:
        return '\r\n'
    if b'\r' in blueprint_excerpt:
        return '\r'
    return '\n'

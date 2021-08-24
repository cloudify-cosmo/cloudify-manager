import difflib
import re
import shutil
import typing
from datetime import datetime, timezone, timedelta
from os import chdir, chmod, environ, listdir, stat
from os.path import exists, isfile, join
from tempfile import TemporaryDirectory, mktemp

import yaml

from dsl_parser import utils as dsl_parser_utils
from dsl_parser.constants import (CLOUDIFY,
                                  IMPORT_RESOLVER_KEY)

from manager_rest import config
from manager_rest.constants import (FILE_SERVER_BLUEPRINTS_FOLDER,
                                    FILE_SERVER_UPLOADED_BLUEPRINTS_FOLDER,
                                    PROVIDER_CONTEXT_ID,
                                    SUPPORTED_ARCHIVE_TYPES)
from manager_rest.flask_utils import (setup_flask_app, set_admin_current_user,
                                      get_tenant_by_name, set_tenant_in_app)
from manager_rest.storage import models


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


def get_resolver(storage_manager):
    cloudify_section = storage_manager.get(
        models.ProviderContext, PROVIDER_CONTEXT_ID).context.get(CLOUDIFY, {})
    resolver_section = cloudify_section.get(IMPORT_RESOLVER_KEY, {})
    resolver_section.setdefault(
        'implementation',
        'manager_rest.'
        'resolver_with_catalog_support:ResolverWithCatalogSupport')
    return dsl_parser_utils.create_import_resolver(resolver_section)


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


def update_blueprint(input_file_name: str, output_file_name: str,
                     start_position: int, end_position: int,
                     replacement: str):
    """Replace input file's content from `start_position` to `end_position`
    with `replacement`, write the output to `output_file_name`."""
    with open(input_file_name, 'rb') as input_file:
        with open(output_file_name, 'wb') as output_file:
            content = input_file.read(start_position - input_file.tell())
            output_file.write(content)
            output_file.write(replacement.encode('utf-8', 'ignore'))
            input_file.read(end_position - start_position)
            content = input_file.read()
            output_file.write(content)


def write_blueprint_diff(from_file_name: str,
                         to_file_name: str,
                         diff_file_name: str):
    def file_mtime(path):
        t = datetime.fromtimestamp(stat(path).st_mtime,
                                   timezone.utc)
        return t.astimezone().isoformat()

    with open(from_file_name, 'r') as from_file:
        from_lines = from_file.readlines()
    with open(to_file_name, 'r') as to_file:
        to_lines = to_file.readlines()
    diff = difflib.context_diff(
        from_lines,
        to_lines,
        from_file_name,
        to_file_name,
        file_mtime(from_file_name),
        file_mtime(to_file_name)
    )
    with open(diff_file_name, 'w') as diff_file:
        diff_file.writelines(diff)


def format_from_file_name(file_name: str) -> typing.Optional[str]:
    file_name_split = file_name.split('.')
    if file_name_split[-1].upper() == 'ZIP':
        return 'zip'
    if file_name_split[-1].upper() == 'TAR':
        return 'tar'
    if file_name_split[-1].upper() == 'TBZ2' or \
            (file_name_split[-2].upper() == 'TAR' and
             file_name_split[-1].upper() == 'BZ2'):
        return 'bztar'
    if file_name_split[-1].upper() == 'TGZ' or \
            (file_name_split[-2].upper() == 'TAR' and
             file_name_split[-1].upper() == 'GZ'):
        return 'gztar'
    return None


def update_archive(blueprint: models.Blueprint, updated_file_name: str):
    blueprint_archive_file_name = archive_file_name(blueprint)
    archive_format = format_from_file_name(blueprint_archive_file_name)
    if not archive_format:
        raise UpdateException('Unknown archive format: {0}'.format(
            blueprint_archive_file_name))
    with TemporaryDirectory() as working_dir:
        chdir(working_dir)
        shutil.unpack_archive(blueprint_archive_file_name, working_dir)
        archive_base_dir = listdir(working_dir)[0]
        shutil.copy(updated_file_name,
                    join(working_dir,
                         archive_base_dir,
                         blueprint.main_file_name))
        new_archive_base = mktemp()
        new_archive_file_name = shutil.make_archive(new_archive_base,
                                                    archive_format,
                                                    root_dir=working_dir)
        shutil.move(new_archive_file_name, blueprint_archive_file_name)
        chmod(blueprint_archive_file_name, 0o644)


def parse_time_interval(interval: str) -> timedelta:
    m = re.match(r'^(\d+)\ (\w+)$', interval)
    if len(m.groups()) != 2:
        return None
    count = int(m.groups()[0])
    unit = m.groups()[1].lower()
    if unit.startswith('s'):
        return timedelta(seconds=count)
    elif unit.startswith('m'):
        return timedelta(minutes=count)
    elif unit.startswith('h'):
        return timedelta(hours=count)
    elif unit.startswith('d'):
        return timedelta(days=count)
    elif unit.startswith('w'):
        return timedelta(weeks=count)
    return None

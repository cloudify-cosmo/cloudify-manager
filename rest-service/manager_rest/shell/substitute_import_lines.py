"""Substitute import lines in blueprints, based on hardcoded mapping"""
import logging
import shutil
import sys
import typing
from os.path import basename

import click
import yaml

from manager_rest.flask_utils import get_tenant_by_name, set_tenant_in_app
from manager_rest.shell import common
from manager_rest.storage import models, get_storage_manager


class Mapping:
    def __init__(self, src: typing.List[str], dst: typing.List[str]):
        self._from = src
        self._to = dst

    def matches(self, imports: typing.List[str]) -> bool:
        if len(imports) != len(self._from):
            return False
        return all(part in self._from for part in imports) \
            and all(part in imports for part in self._from)

    def replacement(self, separator='\n'):
        replacement = separator.join(f'  - {line}' for line in self._to)
        return f'{separator}{replacement}'


DEFAULT_MAPPING = [
    Mapping(src=['https://example.com/cloudify/5.1.0/types/linux-type.yaml',
                 'https://example.com/cloudify/5.1.0/types/foo-type.yaml'],
            dst=['https://www.getcloudify.org/spec/cloudify/5.1.0/types.yaml',
                 'plugin:example-deploy-plugin',
                 'plugin:example-linux',
                 'plugin:example-foo']),
]


def load_mappings(file_name: str) -> typing.List[Mapping]:
    try:
        with open(file_name, 'r') as mapping_file:
            try:
                mappings = [Mapping(src=m['from'], dst=m['to'])
                            for m in yaml.safe_load(mapping_file)]
            except yaml.YAMLError as ex:
                raise common.UpdateException(
                    'Cannot load mappings from {0}: {1}'.format(file_name, ex))
    except OSError as ex:
        raise common.UpdateException(
            'Mappings file {0} cannot be read: {1}'.format(file_name, ex))
    return mappings


def find_mapping(blueprint: models.Blueprint,
                 mappings: typing.List[Mapping],
                 ) -> typing.Optional[Mapping]:
    file_name = common.blueprint_file_name(blueprint)
    with open(file_name, 'r') as blueprint_file:
        try:
            imports = yaml.safe_load(blueprint_file).get('imports', [])
        except yaml.YAMLError as ex:
            raise common.UpdateException(
                'Cannot load blueprint {0}: {1}'.format(file_name, ex))

    for mapping in mappings:
        if mapping.matches(imports):
            return mapping

    return None


def correct_blueprint(blueprint: models.Blueprint,
                      mapping: Mapping):
    """Replace `blueprint`'s import lines with those defined by `mapping`.
    Moreover create a diff file which stores modification details and also
    update blueprint's archive."""
    file_name = common.blueprint_file_name(blueprint)
    new_file_name = common.blueprint_updated_file_name(blueprint)
    try:
        with open(file_name, 'rb') as blueprint_file:
            start_at, end_at = common.get_imports_position(blueprint_file)
            separator = common.get_line_separator(blueprint_file)
    except (FileNotFoundError, PermissionError) as ex:
        raise common.UpdateException(
            'Cannot load blueprint from {0}: {1}'.format(file_name, ex))

    try:
        common.update_blueprint(file_name, new_file_name, start_at, end_at,
                                mapping.replacement(separator))
    except OSError as ex:
        raise common.UpdateException(
            'Cannot update blueprint into {0}: {1}'.format(new_file_name, ex))

    diff_file_name = common.blueprint_diff_file_name(blueprint)
    try:
        common.write_blueprint_diff(file_name, new_file_name, diff_file_name)
    except OSError as ex:
        raise common.UpdateException(
            'Cannot create a diff file {0}: {1}'.format(diff_file_name, ex))

    try:
        common.update_archive(blueprint, new_file_name)
    except OSError as ex:
        fn = common.archive_file_name(blueprint)
        raise common.UpdateException(
            'Cannot update the blueprint archive {0}: {1}'.format(fn, ex))

    try:
        shutil.move(new_file_name, file_name)
    except OSError as ex:
        raise common.UpdateException(
            'Cannot update the blueprint file {0}: {1}'.format(file_name, ex))


@click.command()
@click.option('-a', '--all-tenants', is_flag=True,
              help='Include resources from all tenants.', )
@click.option('-t', '--tenant-name', 'tenant_names', multiple=True,
              help='Tenant name; mutually exclusivele with --all-tenants.', )
@click.option('-b', '--blueprint', 'blueprint_ids',
              multiple=True, help='Blueprint(s) to update (you can provide '
                                  'multiple --blueprint(s).')
@click.option('--mapping', 'mapping_file',
              help='Provide a mapping defining import lines substitutions.')
def main(all_tenants, tenant_names, blueprint_ids, mapping_file):
    logging.basicConfig(
        format='%(asctime)s.%(msecs)03d %(levelname)s '
               '[%(module)s.%(funcName)s] %(message)s',
        datefmt='%H:%M:%S',
        level=logging.INFO)
    logger = logging.getLogger(basename(sys.argv[0]))

    if all_tenants and tenant_names:
        logger.critical('--all-tenants and --tenant-name options are '
                        'mutually exclusive')
        sys.exit(1)
    if not tenant_names:
        tenant_names = (common.DEFAULT_TENANT,)

    common.setup_environment()
    sm = get_storage_manager()
    tenants = sm.list(models.Tenant, get_all_results=True) if all_tenants \
        else [get_tenant_by_name(name) for name in tenant_names]
    blueprint_filter = {'state': 'uploaded'}
    if blueprint_ids:
        blueprint_filter['id'] = blueprint_ids
    mappings = load_mappings(mapping_file) if mapping_file else DEFAULT_MAPPING

    for tenant in tenants:
        set_tenant_in_app(get_tenant_by_name(tenant.name))
        sm = get_storage_manager()
        blueprints = sm.list(
            models.Blueprint,
            filters=blueprint_filter,
            get_all_results=True
        )

        for blueprint in blueprints:
            try:
                mapping = find_mapping(blueprint, mappings)
                if mapping:
                    logger.info("Updating tenant's `%s` blueprint `%s`",
                                blueprint.tenant.name, blueprint.id)
                    correct_blueprint(blueprint, mapping)
                else:
                    logger.debug("Tenant's `%s` blueprint does not require "
                                 "upgrading: `%s`",
                                 blueprint.tenant.name, blueprint.id)
            except common.UpdateException as ex:
                logger.error("Error updating tenant's `%s` blueprint `%s`: %s",
                             blueprint.tenant.name, blueprint.id, ex)

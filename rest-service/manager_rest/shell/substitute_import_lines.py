"""Substitute import lines in blueprints, based on hardcoded mapping"""
from copy import copy
from os.path import basename, join
import sys
import typing

import click
import logging
import yaml

from manager_rest.flask_utils import get_tenant_by_name, set_tenant_in_app
from manager_rest.shell import common
from manager_rest.storage import models, get_storage_manager

DEFAULT_TENANT = 'default_tenant'
REST_HOME_DIR = '/opt/manager'
REST_CONFIG_PATH = join(REST_HOME_DIR, 'cloudify-rest.conf')
REST_SECURITY_CONFIG_PATH = join(REST_HOME_DIR, 'rest-security.conf')


class Mapping:
    def __init__(self, src: typing.List[str], dst: typing.List[str]):
        self._from = src
        self._to = dst

    def __str__(self):
        def get_list_repr(items: typing.List[str], n=32) -> str:
            def first_n(s: str, n=32) -> str:
                return f'{s[:n - 3]}...' if len(s) > n - 3 else s
            if len(items) < 1:
                return 'empty'
            elif len(items) == 1:
                return first_n(items[0], n)
            else:
                return first_n(f'{items[0]}, ...', n)
        return f'Mapping [{get_list_repr(self._from)}] → ' \
               f'[{get_list_repr(self._to)}]'

    def matches(self, imports: typing.List[str]) -> bool:
        if len(imports) != len(self._from):
            return False
        imports_copy = copy(imports)
        while imports_copy:
            if imports_copy.pop() not in self._from:
                return False
        return len(imports_copy) == 0

    def replacement(self, separator='\n'):
        replacement = separator.join([f'  - {line}' for line in self._to])
        return f'{separator}{replacement}'


DEFAULT_MAPPING = [
    Mapping(['http://repo/get/cloudify/4.3/td/types/td-linux-type.yaml',
             'http://repo/get/cloudify/4.3/td/types/td-openstack-type.yaml',
             'http://repo/get/cloudify/4.3/td/types/td-pm2-type.yaml'],
            ['http://repo/get/cloudify/4.3/cloudify/types/types.yaml',
             'plugin:td-deploy-plugin-central',
             'plugin:td-deploy-plugin',
             'plugin:cloudify-openstack-plugin']),
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
    except (FileNotFoundError, PermissionError):
        raise common.UpdateException(
            'Mappings file {0} cannot be read'.format(file_name))
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


def update_blueprint(input_file_name: str, output_file_name: str,
                     start_at: int, end_at: int,
                     replacement: str):
    with open(input_file_name, 'rb') as input_file:
        with open(output_file_name, 'wb') as output_file:
            content = input_file.read(start_at - input_file.tell())
            output_file.write(content)
            output_file.write(replacement.encode('utf-8', 'ignore'))
            input_file.read(end_at - start_at)
            content = input_file.read()
            output_file.write(content)


def correct_blueprint(blueprint: models.Blueprint,
                      mapping: Mapping):
    file_name = common.blueprint_file_name(blueprint)
    new_file_name = common.blueprint_updated_file_name(blueprint)
    try:
        with open(file_name, 'rb') as blueprint_file:
            start_at, end_at = common.get_imports_position(blueprint_file)
            separator = common.get_line_separator(blueprint_file)
    except (FileNotFoundError, PermissionError) as ex:
        raise common.UpdateException('Cannot load blueprint from {0}: {1}'
                                     .format(file_name, ex))
    update_blueprint(file_name, new_file_name, start_at, end_at,
                     mapping.replacement(separator))


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
        exit(1)
    if not tenant_names:
        tenant_names = (DEFAULT_TENANT,)

    common.setup_environment()
    sm = get_storage_manager()
    tenants = sm.list(models.Tenant, get_all_results=True) if all_tenants \
        else [get_tenant_by_name(name) for name in tenant_names]
    blueprint_filter = {
        'tenant': None,
        'state': 'uploaded',
    }
    if blueprint_ids:
        blueprint_filter['id'] = blueprint_ids
    mappings = load_mappings(mapping_file) if mapping_file else DEFAULT_MAPPING

    for tenant in tenants:
        set_tenant_in_app(get_tenant_by_name(tenant.name))
        sm = get_storage_manager()
        blueprint_filter['tenant'] = tenant
        blueprints = sm.list(
            models.Blueprint,
            filters=blueprint_filter,
            get_all_results=True
        )

        for blueprint in blueprints:
            try:
                mapping = find_mapping(blueprint, mappings)
                if mapping:
                    logger.info(f"Updating tenant's `{tenant.name}` "
                                f"blueprint `{blueprint.id}`")
                    correct_blueprint(blueprint, mapping)
                else:
                    logger.debug(f"Tenant's `{tenant.name}` blueprint does "
                                 f"not require upgrading: `{blueprint.id}`")
            except common.UpdateException as ex:
                logger.error(f"Error updating tenant's {tenant.name} "
                             f"blueprint {blueprint.id}: {ex}")


if __name__ == '__main__':
    main()

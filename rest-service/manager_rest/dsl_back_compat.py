import os

import yaml

from dsl_parser.constants import TYPES_BASED_ON_DB_ENTITIES


def create_bc_plugin_yaml(yamls, archive_target_path, logger):
    if not yamls:
        raise RuntimeError("At least one yaml file must be provided")

    if any(filename.endswith('_1_3.yaml') for filename in yamls):
        return None, None

    # take the first yaml file - this is the default behaviour
    with open(yamls[0]) as fh:
        try:
            plugin_yaml = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            raise RuntimeError(f"The provided plugin's description "
                               f"({yamls[0]}) can not be read.\n{e}")
    modifications_required = False
    for selector in [
        ('data_types', '*', 'properties', '*'),
        ('inputs', '*'),
        ('node_types', '*', 'properties', '*'),
        ('relationships', '*', 'source_interfaces', '*', '*', 'inputs', '*'),
        ('relationships', '*', 'target_interfaces', '*', '*', 'inputs', '*'),
        ('workflows', '*', 'parameters', '*'),
    ]:
        nodes = _nodes_in_tree(plugin_yaml, selector)
        if not nodes:
            continue
        for path, element in nodes.items():
            if not element or not isinstance(element, dict):
                continue
            if element.get('type') in TYPES_BASED_ON_DB_ENTITIES:
                _substitute_tree_node(
                    plugin_yaml, path + ('type', ), 'string')
                _remove_tree_node(
                    plugin_yaml, path + ('constraints', ))
                modifications_required |= True

    for selector in [
        ('workflows', '*', 'availability_rules'),
    ]:
        nodes = _nodes_in_tree(plugin_yaml, selector)
        if not nodes:
            continue
        for path, rules in nodes.items():
            if not rules or not isinstance(rules, dict):
                continue
            _remove_tree_node(plugin_yaml, path)
            modifications_required |= True

    if modifications_required:
        save_bc_plugin_yaml(
            os.path.join(archive_target_path, 'plugin_1_3.yaml'),
            plugin_yaml
        )
        logger.info('backward compatible plugin yaml created')


def save_bc_plugin_yaml(file_path, plugin_yaml):
    with open(file_path, 'w') as fh:
        yaml.safe_dump(plugin_yaml, fh)


def _nodes_in_tree(data, path):
    """Find leafs of `data` pointed by `path`.

    >>> _nodes_in_tree( \
            {'a': {'b': {'q': 1, 'w': 2}, 'c': {'q': 3, 'w': 4}}}, \
            ('a', '*', 'w') \
        ) == {('a', 'b', 'w'): 2, ('a', 'c', 'w'): 4}
    """
    def merge(n, d, last=False):
        if not isinstance(d, dict) or last:
            return {(n, ): d}
        else:
            return {(n, ) + k if isinstance(k, tuple) else (k, ): v
                    for k, v in d.items()}

    if not data or not path:
        return data
    path_head, *path_tail = path
    if path_head in data:
        return merge(path_head,
                     _nodes_in_tree(data[path_head], path_tail),
                     not path_tail)
    if path_head == '*' and isinstance(data, dict):
        result = {}
        for r in [merge(k, _nodes_in_tree(v, path_tail), not path_tail)
                  for k, v in data.items()]:
            result.update(r)
        return result


def _remove_tree_node(data, path):
    """Removes a leaf of `data` pointed by `path`.

    >>> _remove_tree_node( \
            {'a': {'b': {'q': 1, 'w': 2}, 'c': 3}}, \
            ('a', 'b', 'w') \
        ) == {'a': {'b': {'q': 1}, 'c': 3}}
    """
    if not path or not data:
        return
    path_head, *path_tail = path
    if path_head not in data:
        return
    if not path_tail:
        del data[path_head]
    else:
        _remove_tree_node(data[path_head], path_tail)


def _substitute_tree_node(data, path, value):
    """Substitutes a leaf of `data` pointed by `path` with a `value`.

    data=
    >>> _substitute_tree_node( \
            {'a': {'q': 1, 'w': 2}, 'b': 3}, \
            ('a', 'w'), \
            9 \
        ) == {'a': {'q': 1, 'w': 9}, 'b': 3}
    """
    if not path or not data:
        return
    path_head, *path_tail = path
    if path_head not in data:
        return
    if not path_tail:
        data[path_head] = value
    else:
        _substitute_tree_node(data[path_head], path_tail, value)

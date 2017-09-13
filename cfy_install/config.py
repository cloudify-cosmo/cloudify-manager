import json
import collections
from os.path import join, dirname as up

_config = None


def dict_merge(dct, merge_dct):
    """ Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested
    to an arbitrary depth, updating keys. The ``merge_dct`` is merged into
    ``dct``.
    Taken from: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9
    :param dct: dict onto which the merge is executed
    :param merge_dct: dct merged into dct
    :return: None
    """
    for k, v in merge_dct.iteritems():
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
            dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]


class Config(dict):
    def __init__(self):
        super(Config, self).__init__()
        base_dir_path = up(up(__file__))
        defaults_path = join(base_dir_path, 'defaults.json')
        config_path = join(base_dir_path, 'config.json')

        with open(defaults_path, 'r') as f:
            self.update(json.load(f))

        # Override any default values with values from config.json
        with open(config_path, 'r') as f:
            dict_merge(self, json.load(f))

    def _add_files_to_clean(self, key, new_paths_to_remove):
        if not isinstance(new_paths_to_remove, (list, tuple)):
            new_paths_to_remove = [new_paths_to_remove]
        paths_to_remove = self.setdefault(key, [])
        paths_to_remove.extend(new_paths_to_remove)

    def add_temp_files_to_clean(self, new_paths_to_remove):
        self._add_files_to_clean(
            'temp_paths_to_remove',
            new_paths_to_remove
        )

    def add_teardown_files_to_clean(self, new_paths_to_remove):
        self._add_files_to_clean(
            'teardown_paths_to_remove',
            new_paths_to_remove
        )


def _get_config():
    global _config
    if not _config:
        _config = Config()
    return _config


config = _get_config()

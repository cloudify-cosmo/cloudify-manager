import json
import collections
from os.path import join, dirname as up

from .utils.common import run
from .constants import CLOUDIFY_BOOTSTRAP_DIR

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
    BS_CONFIG_PATH = join(CLOUDIFY_BOOTSTRAP_DIR, 'bs_config.json')

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

    def dump_config(self):
        with open(self.BS_CONFIG_PATH, 'w') as f:
            json.dump(self, f)

        # Make the bootstrap config file readonly
        run(['chmod', '-wx', self.BS_CONFIG_PATH])

    def load_bootstrap_config(self):
        defaults_path = join(up(up(__file__)), 'defaults.json')
        config_path = join(CLOUDIFY_BOOTSTRAP_DIR, 'config.json')

        with open(defaults_path, 'r') as f:
            self.update(json.load(f))

        # Override any default values with values from config.json
        with open(config_path, 'r') as f:
            dict_merge(self, json.load(f))

    def load_teardown_config(self):
        with open(self.BS_CONFIG_PATH, 'r') as f:
            self.update(json.load(f))


def _get_config():
    global _config
    if not _config:
        _config = Config()
    return _config


config = _get_config()

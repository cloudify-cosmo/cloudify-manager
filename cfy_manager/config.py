import yaml
import collections
from os.path import isfile

from .constants import USER_CONFIG_PATH, DEFAULT_CONFIG_PATH

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
    def __init__(self, *args, **kwargs):
        super(Config, self).__init__(*args, **kwargs)

        with open(DEFAULT_CONFIG_PATH, 'r') as f:
            self.update(yaml.load(f))

        # Allow `config.yaml` not to exist - this is normal for teardown
        if isfile(USER_CONFIG_PATH):
            # Override any default values with values from config.yaml
            with open(USER_CONFIG_PATH, 'r') as f:
                dict_merge(self, yaml.load(f))

    def add_temp_path_to_clean(self, new_path_to_remove):
        paths_to_remove = self.setdefault('temp_paths_to_remove', [])
        paths_to_remove.append(new_path_to_remove)


def _get_config():
    global _config
    if not _config:
        _config = Config()
    return _config


config = _get_config()

from __future__ import print_function
import os
import shutil
import sys


class WrongExtension(Exception):
    pass


def splitext(filename):
    # not using os.path.splitext as it would return .gz instead of .tar.gz
    for ext in ".tar.gz", ".exe":
        if filename.endswith(ext):
            return filename[:-len(ext)], ext
    raise WrongExtension(
        "Unknown agent format for {0}. "
        "Must be either tar.gz or exe".format(filename))


def normalize_agent_name(filename):
    return filename.rpartition("_")[0].lower()


def normalize_names(directory, target_dir):
    previous_targets = set()
    for fn in os.listdir(directory):
        try:
            fn, extension = splitext(fn)
        except WrongExtension:
            # Ignore files with extensions we don't like
            continue
        source = os.path.join(directory, fn + extension)
        target = os.path.join(target_dir, normalize_agent_name(fn) + extension)
        print('copying {} to {}'.format(source, target))
        if target in previous_targets:
            raise RuntimeError(
                'packages normalised to same target path!', target)
        previous_targets.add(target)
        shutil.copy(source, target)


normalize_names(*sys.argv[1:3])

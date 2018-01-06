import os
import sys


def splitext(filename):
    # not using os.path.splitext as it would return .gz instead of .tar.gz
    if filename.endswith(".tar.gz"):
        return ".tar.gz"
    elif filename.endswith(".exe"):
        return ".exe"
    else:
        raise ValueError("Unknown agent format for {0}. "
                         "Must be either tar.gz or exe".format(filename))


def normalize_agent_name(filename):
    return filename.split("_", 1)[0].lower()


def normalize_names(directory):
    for fn in os.listdir(directory):
        extension = splitext(fn)
        os.rename(fn, normalize_agent_name(fn) + extension)


normalize_names(sys.argv[1])

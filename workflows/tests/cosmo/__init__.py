__author__ = 'idanmo'

import fnmatch
import os


def build_includes(workdir, app):
    includes = []
    for root, dirnames, filenames in os.walk(os.path.join(workdir, app)):
        for filename in fnmatch.filter(filenames, 'tasks.py'):
            includes.append(os.path.join(root, filename))

    # remove .py suffix from include
    includes = map(lambda include: include[:-3], includes)

    # remove path prefix to start with cosmo
    includes = map(lambda include: include.replace(workdir, ''), includes)

    # replace slashes with dots in include path
    includes = map(lambda include: include.replace('/', '.'), includes)

    # remove the dot at the start
    includes = map(lambda include: include[1:], includes)

    return includes

includes = build_includes(os.getcwd(), 'cosmo')


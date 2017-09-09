import os
import re
import json
import tempfile
from glob import glob
from os.path import join, isabs

from .common import move, sudo
from .network import is_url, curl_download

from ..logger import get_logger
from ..constants import CLOUDIFY_SOURCES_PATH


logger = get_logger('Files')


def replace_in_file(this, with_this, in_here):
    """Replaces all occurrences of the regex in all matches
    from a file with a specific value.
    """
    logger.debug('Replacing {0} with {1} in {2}...'.format(
        this, with_this, in_here))
    with open(in_here) as f:
        content = f.read()
    new_content = re.sub(this, with_this, content)
    fd, temp_file = tempfile.mkstemp()
    os.close(fd)
    with open(temp_file, 'w') as f:
        f.write(new_content)
    move(temp_file, in_here)


def ln(source, target, params=None):
    logger.debug('Linking {0} to {1} with params {2}'.format(
        source, target, params))
    command = ['ln']
    if params:
        command.append(params)
    command.append(source)
    command.append(target)
    if '*' in source or '*' in target:
        sudo(command, globx=True)
    else:
        sudo(command)


def get_local_source_path(source_url):
    if is_url(source_url):
        return curl_download(source_url)
    # If it's already an absolute path, just return it
    if isabs(source_url):
        return source_url

    # Otherwise, it's a relative `sources` path
    path = join(CLOUDIFY_SOURCES_PATH, source_url)
    if '*' in path:
        matching_paths = glob(path)
        if not matching_paths:
            raise StandardError(
                'Could not locate source matching {0}'.format(source_url)
            )
        if len(matching_paths) > 1:
            raise StandardError(
                'Expected to find single source matching '
                '{0}, but found: {1}'.format(source_url, matching_paths)
            )
        path = matching_paths[0]
    return path


def write_to_tempfile(contents, json_dump=False):
    fd, file_path = tempfile.mkstemp()
    if json_dump:
        contents = json.dumps(contents)

    os.write(fd, contents)
    os.close(fd)
    return file_path


def write_to_file(contents, destination, json_dump=False):
    """ Used to write files to locations that require sudo to access """

    temp_path = write_to_tempfile(contents, json_dump=json_dump)
    move(temp_path, destination)

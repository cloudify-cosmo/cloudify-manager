import os
import re
import json
import tempfile
from glob import glob
from tempfile import mkstemp
from os.path import join, isabs

from .network import is_url, curl_download
from .common import move, sudo, copy, remove

from ..config import config
from ..logger import get_logger
from ..exceptions import FileError
from ..constants import CLOUDIFY_SOURCES_PATH, COMPONENTS_DIR

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
            raise FileError(
                'Could not locate source matching {0}'.format(source_url)
            )
        if len(matching_paths) > 1:
            raise FileError(
                'Expected to find single source matching '
                '{0}, but found: {1}'.format(source_url, matching_paths)
            )
        path = matching_paths[0]
    return path


def write_to_tempfile(contents, json_dump=False, cleanup=True):
    fd, file_path = tempfile.mkstemp()
    if json_dump:
        contents = json.dumps(contents)

    os.write(fd, contents)
    os.close(fd)
    if cleanup:
        config.add_temp_path_to_clean(file_path)
    return file_path


def write_to_file(contents, destination, json_dump=False):
    """ Used to write files to locations that require sudo to access """

    temp_path = write_to_tempfile(contents, json_dump=json_dump, cleanup=False)
    move(temp_path, destination)


def remove_temp_files():
    logger.debug('Cleaning temporary files...')
    for path in config.get('temp_paths_to_remove', []):
        remove(path)
    logger.debug('Cleaned temporary files')


def remove_files(file_list, ignore_failure=False):
    for path in file_list:
        logger.debug('Removing {0}...'.format(path))
        sudo(['rm', '-rf', path], ignore_failures=ignore_failure)


def deploy(src, dst, render=True):
    if render:
        with open(src, 'r') as f:
            content = f.read()
        content = content.format(**config)
        fd, temp_dst = mkstemp()
        os.close(fd)
        with open(temp_dst, 'w') as f:
            f.write(content)
        move(temp_dst, dst)
    else:
        copy(src, dst)


def _get_notice_path(service_name):
    return join('/opt', '{0}_NOTICE.txt'.format(service_name))


def copy_notice(service_name):
    src = join(COMPONENTS_DIR, service_name, 'NOTICE.txt')
    copy(src, _get_notice_path(service_name))


def remove_notice(service_name):
    remove(_get_notice_path(service_name))

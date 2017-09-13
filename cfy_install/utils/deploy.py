import os
from os.path import join
from tempfile import mkstemp

from .common import copy, move

from ..config import config
from ..constants import COMPONENTS_DIR


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


def copy_notice(service_name):
    src = join(COMPONENTS_DIR, service_name, 'NOTICE.txt')
    dst = join('/opt', '{0}_NOTICE.TXT'.format(service_name))
    copy(src, dst)

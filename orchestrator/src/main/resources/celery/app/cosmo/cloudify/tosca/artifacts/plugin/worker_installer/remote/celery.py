from __future__ import absolute_import

from celery import Celery
from cosmo import includes
import sys
import traceback
import os
import cosmo

celery = Celery('cosmo.celery', include=includes)

old_excepthook = sys.excepthook
def new_excepthook(type, value, the_traceback):
    with open(os.path.expanduser('~/celery_error.out'), 'w') as f:
        f.write('Type: {0}\n'.format(type))
        f.write('Value: {0}\n'.format(value))
        traceback.print_tb(the_traceback, file=f)
    old_excepthook(type, value, the_traceback)
sys.excepthook = new_excepthook

def get_management_ip():
    file_path = os.path.join(os.path.dirname(cosmo.__file__), 'management-ip.txt')
    with open(file_path, 'r') as f:
        return f.readlines()[0]

if __name__ == '__main__':
    celery.start()

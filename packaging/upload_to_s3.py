#!/usr/bin/env python
from __future__ import print_function

import os
import subprocess
from StringIO import StringIO

import boto3

build_type = os.environ.get('BUILD_TYPE')
BUCKET = 'cloudify-release-eu'
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_TEMPLATE = 'cloudify/{version}/{build_type}/{name}'

s3 = boto3.client('s3')

for file in os.listdir(THIS_DIR):
    if not file.endswith(".rpm"):
        continue
    file_path = os.path.join(THIS_DIR, file)
    version = subprocess.check_output([
        'rpm', '-qp', '--queryformat', '%{VERSION}', file_path])
    key = KEY_TEMPLATE.format(version=version, name=file)
    md5sum = subprocess.check_output(['md5sum', file], cwd=THIS_DIR)

    s3.upload_file(file_path, BUCKET, key,
                   ExtraArgs={'ACL': 'public-read'})
    s3.upload_fileobj(StringIO(md5sum), BUCKET, key + '.md5',
                      ExtraArgs={'ACL': 'public-read'})
    target_url = 'https://{0}.s3.amazonaws.com/{1}'.format(BUCKET, key)
    print('uploaded {0} ({1}): {2}'
          .format(file, md5sum.split()[0], target_url))

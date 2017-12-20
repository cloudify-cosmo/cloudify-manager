#!/usr/bin/env python
from __future__ import print_function

import os
import subprocess

import boto3


BUCKET = 'cloudify-release-eu'
THIS_DIR = os.path.dirname(os.path.abspath(__file__))


s3 = boto3.resource('s3')

for file in os.listdir(THIS_DIR):
    if file.endswith(".rpm"):
        file_path = os.path.join(THIS_DIR, file)
        md5sum = subprocess.check_output(['md5sum', file_path])
        md5sum_file = file_path + '.md5'
        with open(md5sum_file, 'w') as f:
            f.write(md5sum)

        version = subprocess.check_output([
            'rpm', '-qp', '--queryformat', '%{VERSION}', file_path])

        for name in (file_path, md5sum_file):
            key = 'cloudify/{version}/build/{name}'.format(
                version=version, name=name)
            s3.meta.client.upload_file(name, BUCKET, key)
            print('uploaded', '/'.join((s3.meta.endpoint_url, BUCKET, key)))

#!/usr/bin/env python2
#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import os
import shutil
import argparse

HOME_DIR = "{{ stage.home_dir }}"


def _restore(snapshot_root, override=False):
    for folder in ['conf', 'dist/widgets', 'dist/templates']:
        destination = os.path.join(HOME_DIR, folder)
        if not override:
            destination = os.path.join(destination, 'from_snapshot')
        if os.path.exists(destination):
            shutil.rmtree(destination)
        shutil.copytree(os.path.join(snapshot_root, folder), destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot_root')
    parser.add_argument(
        '--override-existing',
        action='store_true',
        help='Override the existing stage files with the restored files.',
    )
    args = parser.parse_args()
    _restore(args.snapshot_root, override=args.override_existing)
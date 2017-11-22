########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import argparse
import logging
import os
import sys
import tempfile
from subprocess import check_call, check_output


PACKAGING_DIR = os.path.dirname(__file__) or '.'
SSH_CONF_FILE = os.path.join(PACKAGING_DIR, 'ssh_config.tmp')


logger = logging.getLogger(os.path.basename(__file__))


def run(cmd, *args, **kwargs):
    if '_func' in kwargs:
        func = kwargs.pop('_func')
    else:
        func = check_call
    logger.info('running <{cmd}> on vagrant builder'.format(cmd=cmd))
    return func(
            ['vagrant', 'ssh', 'builder', '-c', cmd],
            *args, **kwargs)


def main(args):
    parser = argparse.ArgumentParser(
            description="Build RPM using mock",
            )
    parser.add_argument(
            'spec_file', type=argparse.FileType('r'),
            help="which RPM to build",
            )

    args = parser.parse_args(args)

    os.chdir(os.path.dirname(__file__) or '.')
    check_call(['vagrant', 'up', 'builder'])
    run('sudo yum -y install epel-release')
    run('sudo yum -y install mock')
    run('sudo usermod -a -G mock $USER')
    run('echo -e '
        r'''"\nconfig_opts['rpmbuild_networking'] = True\n" '''
        '| sudo tee -a /etc/mock/site-defaults.cfg')
    run('mock --verbose --buildsrpm --spec '
        '/source/packaging/{spec_file} '
        '--sources /source/'.format(
            spec_file=args.spec_file.name))
    src_rpm = run(
            'find /var/lib/mock/epel-7-x86_64/result -name *.src.rpm',
            _func=check_output,
            ).strip()
    run('mock --verbose --chroot -- chown -R mockbuild /opt')
    run('mock "{src_rpm}" --no-clean'.format(
                src_rpm=src_rpm))

    ssh_config = check_output(
            ['vagrant', 'ssh-config', 'builder'])
    with open(SSH_CONF_FILE, 'w') as f:
        f.write(ssh_config)

    check_call(
            ['scp', '-F', SSH_CONF_FILE,
             'builder:{rpm}'.format(
                 rpm=src_rpm.replace('.src.rpm', '.x86_64.rpm')),
             '.'])


if __name__ == "__main__":
    main(sys.argv[1:])

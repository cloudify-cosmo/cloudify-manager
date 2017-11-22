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
from subprocess import check_call, check_output


logger = logging.getLogger(os.path.basename(__file__))


def run(cmd, *args, **kwargs):
    """Run command on Vagrant box"""
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

    packaging_dir = os.path.dirname(args.spec_file.name) or '.'
    ssh_conf_file = os.path.join(packaging_dir, 'ssh_config.tmp')

    os.chdir(packaging_dir)
    check_call(['vagrant', 'up', 'builder'])
    check_call(['vagrant', 'rsync', 'builder'])
    # EPEL is enabled only for the build system.
    # It is not required on production systems.
    run('sudo yum -y install epel-release')
    run('sudo yum -y install mock')
    # mock requires the user to be in the `mock` group
    run('sudo usermod -a -G mock $USER')
    # allow network access during the build
    # (we have to download packages from pypi)
    run('echo -e '
        r'''"\nconfig_opts['rpmbuild_networking'] = True\n" '''
        '| sudo tee -a /etc/mock/site-defaults.cfg')

    # Build .src.rpm
    run('mock --verbose --buildsrpm --spec '
        '/source/packaging/{spec_file} '
        '--sources /source/'.format(
            spec_file=args.spec_file.name))
    # Extract the .src.rpm file name.
    src_rpm = run(
            'find /var/lib/mock/epel-7-x86_64/result -name *.src.rpm',
            _func=check_output,
            ).strip()

    # mock strongly assumes that root is not required for building RPMs.
    # Here we work around that assumption by changing the onwership of /opt
    # inside the CHROOT to the mockbuild user
    run('mock --verbose --chroot -- chown -R mockbuild /opt')
    # Build the RPM
    run('mock "{src_rpm}" --no-clean'.format(
                src_rpm=src_rpm))

    ssh_config = check_output(
            ['vagrant', 'ssh-config', 'builder'])
    with open(ssh_conf_file, 'w') as f:
        f.write(ssh_config)

    # Download the finished RPM from the Vagrant box to localhost
    check_call(
            ['scp', '-F', ssh_conf_file,
             'builder:{rpm}'.format(
                 rpm=src_rpm.replace('.src.rpm', '.x86_64.rpm')),
             '.'])


if __name__ == "__main__":
    main(sys.argv[1:])

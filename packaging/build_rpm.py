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
import sys
import shutil
from os import chdir, getcwd
from os.path import (
        abspath,
        basename,
        dirname,
        join as path_join,
        split as path_split,
        )
from subprocess import check_call, check_output


VAGRANT_DIR = abspath(dirname(__file__))
SSH_CONFIG_FILE = path_join(VAGRANT_DIR, 'ssh_config.tmp')
logger = logging.getLogger(basename(__file__))


def get_rpmbuild_opts():
    """
    Return a string to be passed to `mock` as the value of --rpmbuild-opts
    """
    # Beware that `version.ini` is already looking a bit too much like an
    # ad-hoc config format. Consider replacing with something more standardised
    # before adding any more features here.
    defines = []
    with open('version_info') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                defines.append(
                        '--define "{}"'.format(line))

    return ' '.join(defines)


def run_vagrant(cmd, *args, **kwargs):
    """Run command on Vagrant box"""
    func = kwargs.pop('_func', check_call)

    logger.info('running <{cmd}> on vagrant builder'.format(cmd=cmd))
    return func(
            ['vagrant', 'ssh', 'builder', '-c', cmd],
            *args, **kwargs)


def run_local(cmd, *args, **kwargs):
    func = kwargs.pop('_func', check_call)
    kwargs.setdefault('shell', True)

    logger.info('running <{cmd}> locally'.format(cmd=cmd))
    return func(cmd, *args, **kwargs)


def main(args):
    parser = argparse.ArgumentParser(
            description="Build RPM using mock",
            )
    parser.add_argument(
            'spec_file', type=argparse.FileType('r'),
            help="which RPM to build",
            )
    parser.add_argument('--local', action='store_true',
                        help='Run locally instead of using vagrant')

    args = parser.parse_args(args)
    run = run_local if args.local else run_vagrant

    spec_file = abspath(args.spec_file.name)
    packaging_dir, spec_file_name = path_split(spec_file)
    # We assume that the spec always lives one dir level below the source
    source = dirname(packaging_dir)

    chdir(VAGRANT_DIR)
    if not args.local:
        check_call(['vagrant', 'up', 'builder'])

        ssh_config = check_output(
                ['vagrant', 'ssh-config', 'builder'])
        with open(SSH_CONFIG_FILE, 'w') as f:
            f.write(ssh_config)

        # sync the code
        check_call(
                ['rsync', '-avz',
                 '-e', 'ssh -F {}'.format(SSH_CONFIG_FILE),
                 '--exclude', '.git',
                 '--exclude', '*.sw[op]',  # vim swap files
                 '--delete', '--delete-excluded',
                 source,
                 'builder:source',
                 ])

        source = path_join('~/source', basename(source))

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

    # Get build options
    rpmbuild_opts = get_rpmbuild_opts()
    logger.info('rpmbuild_opts: ' + rpmbuild_opts)

    # Build .src.rpm
    run('mock --verbose --buildsrpm --spec '
        '{source}/packaging/{spec_file} '
        '--sources {source}/ '
        "--rpmbuild-opts '{rpmbuild_opts}'".format(
            spec_file=spec_file_name,
            rpmbuild_opts=rpmbuild_opts,
            source=source
            )
        )
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
    run('mock "{src_rpm}" '
        '--no-clean '
        "--rpmbuild-opts '{rpmbuild_opts}'".format(
            src_rpm=src_rpm,
            rpmbuild_opts=rpmbuild_opts,
            ))

    # Extract the final .rpm file name.
    final_rpm = run(
            'find /var/lib/mock/epel-7-x86_64/result -name *.x86_64.rpm',
            _func=check_output,
            ).strip()
    # Download the finished RPM from the Vagrant box to localhost
    if args.local:
        filename = basename(final_rpm)
        shutil.move(final_rpm, path_join(getcwd(), filename))
    else:
        check_call(
                ['scp', '-F', SSH_CONFIG_FILE,
                 'builder:{rpm}'.format(rpm=final_rpm),
                 '.'])


if __name__ == "__main__":
    main(sys.argv[1:])

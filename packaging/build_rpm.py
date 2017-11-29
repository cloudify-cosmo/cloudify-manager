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
from os import chdir, listdir
from os.path import (
        abspath,
        basename,
        dirname,
        join as path_join,
        split as path_split,
        )
from subprocess import check_call, check_output, CalledProcessError


LOCAL_REPO_PATH = '~/mock_repo'
DEPENDENCIES_FILE = '{spec_file}.dependencies'
RESULT_DIR = '/var/lib/mock/epel-7-x86_64/result'

SCRIPT_DIR, SCRIPT_NAME = path_split(abspath(__file__))
SSH_CONFIG_FILE = path_join(SCRIPT_DIR, 'ssh_config.tmp')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SCRIPT_NAME)


def get_rpmbuild_defines():
    """
    Return a dictionary of macros from `version_info`
    """
    defines = {}
    with open(path_join(SCRIPT_DIR, 'version_info')) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                k, v = line.split(' ', 1)
                defines[k] = v

    return defines


def render_spec_file(spec_file, defines):
    """
    Apply the defines to the spec file. We don't use `--define` because
    `mock`'s `--rpmbuild-opts` doesn't apply to `--buildsrpm`

    Returns the path to the rendered spec file
    """
    with open(spec_file) as f:
        spec_content = f.read()

    for k, v in defines.items():
        spec_content = spec_content.replace('%{' + k + '}', v)

    spec_file_out = spec_file.replace('.spec', '.rendered.spec')
    with open(spec_file_out, 'w') as f:
        f.write(spec_content)

    return spec_file_out


def run_vagrant(cmd, *args, **kwargs):
    """Run command on Vagrant box"""
    func = kwargs.pop('_func', check_call)

    logger.info('running <{cmd}> on vagrant builder'.format(cmd=cmd))
    return func(
            ['vagrant', 'ssh', 'builder', '-c', cmd],
            *args, **kwargs)


def build_local_yum_repo(run, packaging_dir, spec_file):
    """
    Collect the dependent packages and build a local yum repo for `mock` to use
    """
    run('mkdir ' + LOCAL_REPO_PATH)
    with open('{spec_file}.dependencies'.format(spec_file)) as f:
        for url in f:
            run('cd {local_repo_path} && wget -m {url}')


def build(source, spec_file_name):
    """Builds the RPM"""
    # Get build options
    rpmbuild_defines = get_rpmbuild_defines()
    logger.info('defines', rpmbuild_defines)
    rendered_spec_file = render_spec_file(
            path_join(source, 'packaging', spec_file_name),
            rpmbuild_defines,
            )

    # Build .src.rpm
    check_call(
            ['mock', '--verbose', '--buildsrpm',
             '--spec', rendered_spec_file,
             '--sources', source,
             ]
            )
    # Extract the .src.rpm file name.
    for f in listdir(RESULT_DIR):
        if f.endswith('.src.rpm'):
            src_rpm = path_join(RESULT_DIR, f)
            break
    else:
        raise RuntimeError('src rpm not found')

    # mock strongly assumes that root is not required for building RPMs.
    # Here we work around that assumption by changing the onwership of /opt
    # inside the CHROOT to the mockbuild user
    check_call([
            'mock', '--verbose', '--chroot', '--',
            'chown', '-R', 'mockbuild', '/opt'
            ])
    # Build the RPM
    check_call([
            'mock', src_rpm,
            '--no-clean',
            ])

    # Extract the final .rpm file name.
    for f in listdir(RESULT_DIR):
        if f.endswith('.x86_64.rpm'):
            final_rpm = path_join(RESULT_DIR, f)
            break
    else:
        raise RuntimeError('final rpm not found')

    return final_rpm


def has_cmd(cmd):
    try:
        check_call(['which', cmd])
        return True
    except CalledProcessError:
        return False


def install_mock():
    # EPEL is enabled only for the build system.
    # It is not required on production systems.
    run_vagrant('sudo yum -y install epel-release')
    run_vagrant('sudo yum -y install mock')

    # mock requires the user to be in the `mock` group
    run_vagrant('sudo usermod -a -G mock $USER')

    # allow network access during the build
    # (we have to download packages from pypi)
    run_vagrant(
            'echo -e '
            r'''"\nconfig_opts['rpmbuild_networking'] = True\n" '''
            '| sudo tee -a /etc/mock/site-defaults.cfg')


def main(args):
    parser = argparse.ArgumentParser(
            description="Build RPM using mock",
            )
    parser.add_argument(
            'spec_file', type=argparse.FileType('r'),
            help="which RPM to build",
            )

    args = parser.parse_args(args)

    spec_file = abspath(args.spec_file.name)
    packaging_dir, spec_file_name = path_split(spec_file)
    # We assume that the spec always lives one dir level below the source
    source = dirname(packaging_dir)

    chdir(SCRIPT_DIR)

    if has_cmd('mock'):
        # run locally
        rpm = build(source, spec_file_name)
        shutil.copy(rpm, packaging_dir)
    elif has_cmd('vagrant'):
        # install and run mock in a vagrant CentOS 7 box
        check_call(['vagrant', 'up', 'builder'])

        ssh_config = check_output(
                ['vagrant', 'ssh-config', 'builder'])
        with open(SSH_CONFIG_FILE, 'w') as f:
            f.write(ssh_config)

        install_mock()
        # sync the code
        for local, remote in (
                (source, 'source'),
                (SCRIPT_DIR + '/', 'build_script')):
            check_call(
                    ['rsync', '-avz',
                     '-e', 'ssh -F {}'.format(SSH_CONFIG_FILE),
                     '--exclude', '.git',
                     '--exclude', '*.sw[op]',  # vim swap files
                     '--delete', '--delete-excluded',
                     local,
                     'builder:' + remote,
                     ])

        source = path_join('source', basename(source))

        run_vagrant(
                'python "{this_script}" "{spec_file}"'.format(
                    this_script=path_join('build_script', SCRIPT_NAME),
                    spec_file=path_join(source, 'packaging', spec_file_name),
                ))

        # Copy files back
        final_rpm = run_vagrant(
            'find /var/lib/mock/epel-7-x86_64/result -name *.x86_64.rpm',
            _func=check_output,
            ).strip()
        check_call(
                ['scp', '-F', SSH_CONFIG_FILE,
                 'builder:{rpm}'.format(rpm=final_rpm),
                 '.'])

        # Power down the vagrant box
        check_call(['vagrant', 'halt', 'builder'])

    else:
        raise RuntimeError('need either mock or vagrant to build')


if __name__ == "__main__":
    main(sys.argv[1:])

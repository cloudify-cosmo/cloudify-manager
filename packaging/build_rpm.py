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
import urllib2
from datetime import datetime
from os import chdir, listdir
from os.path import (
        abspath,
        basename,
        dirname,
        getmtime,
        join as path_join,
        split as path_split,
        )
from subprocess import check_call, check_output, CalledProcessError


MOCK = '/usr/bin/mock'
LOCAL_REPO_PATH = '~/mock_repo'
DEPENDENCIES_FILE = '{spec_file}.dependencies'
RESULT_DIR = '/var/lib/mock/epel-7-x86_64/result'

SCRIPT_DIR, SCRIPT_NAME = path_split(abspath(__file__))
SSH_CONFIG_FILE = path_join(SCRIPT_DIR, 'ssh_config.tmp')

RPMS_DIR = SCRIPT_DIR

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


def install_dependencies(spec_file):
    """
    Check for and install any internal dependencies.

    Place dependencies, one package name per line, in a file called
    '<spec_file_name>.dependencies'

    e.g.:
        $ cat cloudify-premium/packages/cloudify-premium.spec.dependencies
        cloudify-rest-service
    """
    dependencies_file = DEPENDENCIES_FILE.format(spec_file=spec_file)

    try:
        with open(dependencies_file) as f:
            dependencies = f.readlines()
    except IOError:
        logger.info(
                'no dependencies file found. skipping dependencies install '
                '(this is only required for internal cloudify dependencies)')
        return

    logger.info(
            'installing dependencies from <{file}>. RPMs dir: {dir}'.format(
                file=dependencies_file,
                dir=RPMS_DIR,
                ))

    rpms = {}
    for f in listdir(RPMS_DIR):
        f = f.strip()
        if f.endswith('.x86_64.rpm'):
            name = check_output([
                'rpm', '-qp', '--queryformat', '%{NAME}', f,
                ])
            rpms[name] = f

    logger.info(('found RPMs:', rpms))

    for dep in dependencies:
        dep = dep.strip()
        install_package = rpms[dep]
        check_call([MOCK, '--yum-cmd', 'remove', dep])
        check_call([
            MOCK, '--yum-cmd', 'install', install_package,
            ])


def build(source, spec_file_name):
    """Builds the RPM"""
    spec_file = path_join(source, 'packaging', spec_file_name)
    check_mock_config()
    # Get build options
    rpmbuild_defines = get_rpmbuild_defines()
    logger.info('defines', rpmbuild_defines)
    rendered_spec_file = render_spec_file(spec_file, rpmbuild_defines)

    # Build .src.rpm
    check_call(
            [MOCK, '--verbose', '--buildsrpm',
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

    # Install our internal dependencies
    install_dependencies(spec_file)

    # mock strongly assumes that root is not required for building RPMs.
    # Here we work around that assumption by changing the onwership of /opt
    # inside the CHROOT to the mockbuild user
    check_call([
            MOCK, '--verbose', '--chroot', '--',
            'chown', '-R', 'mockbuild', '/opt'
            ])
    # Build the RPM
    check_call([
            MOCK, src_rpm,
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


def check_mock_config():
    # allow network access during the build
    # (we have to download packages from pypi)
    mock_config = check_output([
        MOCK, '--debug-config',
        ]).splitlines()

    for line in mock_config:
        if all(s in line for s in ('rpmbuild_networking', 'True')):
            break
    else:
        logger.info('configuring rpmbuild_networking')
        check_call(
                '''echo "config_opts['rpmbuild_networking'] = True" '''
                '| sudo -n tee -a /etc/mock/site-defaults.cfg',
                shell=True,
                )


def download_if_newer(url, outfile=None):
    """Check the modified time and ask the server if the file has changed"""
    if not outfile:
        outfile = basename(url)
    headers = {}
    try:
        mod_time = getmtime(outfile)
    except OSError:
        pass
    else:
        headers['If-Modified-Since'] = datetime.utcfromtimestamp(
                mod_time).strftime('%a, %d %b %Y %H:%M:%S GMT')

    req = urllib2.Request(url, headers=headers)
    try:
        try:
            f = urllib2.urlopen(req)
        except urllib2.HTTPError as f:
            if f.getcode() == 304:
                return
            else:
                raise
        with open(outfile, 'wb') as out:
            print('writing', outfile)
            out.write(f.read())
    finally:
        f.close()


def get_sources(spec_file):
    sources = []
    with open(spec_file) as f:
        for line in f:
            key, sep, value = line.strip().partition(':')
            if sep and key.strip().lower().startswith('source'):
                sources.append(value.strip())

    return sources


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

    # Fetch any defined Sources (this does not include the repo containing the
    # spec file itself, the local copy is to be used.
    chdir(source)
    sources = get_sources(spec_file)
    for url in sources:
        download_if_newer(url)

    chdir(SCRIPT_DIR)

    if has_cmd('mock'):
        # run locally
        rpm = build(source, spec_file_name)
        shutil.copy(rpm, SCRIPT_DIR)
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
            "find /var/lib/mock/epel-7-x86_64/result -name '*.x86_64.rpm'",
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

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
from errno import EEXIST
from os import chdir, listdir, makedirs
from os.path import (
        abspath,
        basename,
        dirname,
        expanduser,
        getmtime,
        join as path_join,
        split as path_split,
        )
from subprocess import check_call, check_output, CalledProcessError
from textwrap import dedent


MOCK = ['/usr/bin/mock', '--root', 'epel-7-x86_64', '--verbose']
LOCAL_REPO_PATH = '~/mock_repo'
DEPENDENCIES_FILE = '{spec_file}.dependencies'
RESULT_DIR = '/var/lib/mock/epel-7-x86_64/result'

SCRIPT_DIR, SCRIPT_NAME = path_split(abspath(__file__))
SSH_CONFIG_FILE = path_join(SCRIPT_DIR, 'ssh_config.tmp')

RPMS_DIR = SCRIPT_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(SCRIPT_NAME)


def main(args):
    parser = argparse.ArgumentParser(
            description=dedent("""\
                Build RPM using mock

                If mock is not installed locally,
                Vagrant will be used to build and
                configure a mock build VM

                Requirements:
                  mock (on an EL7 host, from epel-release)
                or
                  vagrant, rsync
            """),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            )
    parser.add_argument(
            'spec_file', type=argparse.FileType('r'),
            help="which RPM spec file to build",
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
    sources += get_dependency_urls(spec_file)
    logger.info(sources)
    for url in sources:
        download_if_newer(url)

    chdir(SCRIPT_DIR)

    if has_cmd('mock'):
        # run locally
        rpm = build(source, spec_file_name)
        shutil.copy(rpm, SCRIPT_DIR)
    elif has_cmd('vagrant'):
        # install and run mock in a vagrant CentOS 7 box
        build_in_vagrant(source, spec_file_name)

    else:
        raise RuntimeError('need either mock or vagrant to build')


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
            MOCK + ['--buildsrpm',
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
    install_dependencies(spec_file, source)

    # mock strongly assumes that root is not required for building RPMs.
    # Here we work around that assumption by changing the onwership of /opt
    # inside the CHROOT to the mockbuild user
    check_call(
            MOCK + ['--verbose', '--chroot', '--',
            'chown', '-R', 'mockbuild', '/opt'
            ])
    # Build the RPM
    check_call(MOCK + ['--verbose', '--no-clean', src_rpm])

    # Extract the final .rpm file name.
    for f in listdir(RESULT_DIR):
        if f.endswith('.x86_64.rpm') or f.endswith('.noarch.rpm'):
            final_rpm = path_join(RESULT_DIR, f)
            break
    else:
        raise RuntimeError('final rpm not found')

    return final_rpm


def build_in_vagrant(source, spec_file_name):
    """
    run this script inside a Vagrant box
    where `mock` is installed and configured
    """
    try:
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
            "find /var/lib/mock/epel-7-x86_64/result "
            "-name '*.noarch.rpm' -o -name '*.x86_64.rpm'",
            _func=check_output,
            ).strip()
        check_call(
                ['scp', '-F', SSH_CONFIG_FILE,
                 'builder:{rpm}'.format(rpm=final_rpm),
                 '.'])

    finally:
        # Power down the vagrant box
        check_call(['vagrant', 'halt', 'builder'])


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


def get_dependencies(spec_file):
    """get the list of dependencies"""
    dependencies_file = DEPENDENCIES_FILE.format(spec_file=spec_file)

    try:
        with open(dependencies_file) as f:
            dependencies = f.readlines()
    except IOError:
        logger.info(
                'no dependencies file found. skipping dependencies install '
                '(this is only required for internal cloudify dependencies)')
        dependencies = []

    return dependencies


def install_dependencies(spec_file, source):
    """
    Check for and install any internal dependencies.

    Place dependencies, one package name per line, in a file called
    '<spec_file_name>.dependencies'

    e.g.:
        $ cat cloudify-premium/packages/cloudify-premium.spec.dependencies
        cloudify-rest-service
    """
    dependencies = get_dependencies(spec_file)

    if not dependencies:
        return

    logger.info(
            'installing dependencies from <{file}>. RPMs dir: {dir}'.format(
                file=DEPENDENCIES_FILE.format(spec_file=spec_file),
                dir=RPMS_DIR,
                ))

    # Collect details about the local RPMs in RPMS_DIR
    rpms = {}
    for f in listdir(RPMS_DIR):
        f = f.strip()
        if any(f.endswith(y) for y in ('.x86_64.rpm', '.noarch.rpm')):
            name = check_output([
                'rpm', '-qp', '--queryformat', '%{NAME}', f,
                ])
            rpms[name] = f
            logger.info('found RPM: {name}: {filename}'.format(
                name=name, filename=f))

    # Install the dependencies from the dependencies file
    for dep in dependencies:
        dep = dep.strip()
        if '://' in dep:
            package_name = check_output([
                    'rpm', '-qp', '--queryformat', '%{NAME}', dep,
                    ])
            # found a URL, install by basename
            install_package = path_join(source, basename(dep))
        else:
            package_name = dep
            # found a package name, lookup in rpms dict
            install_package = rpms[dep]

        check_call(MOCK + ['--yum-cmd', 'remove', package_name])
        check_call(MOCK + ['--yum-cmd', 'install', install_package])


def get_dependency_urls(spec_file):
    """extract lines which contain URLs from the spec.dependencies file"""
    dependencies = get_dependencies(spec_file)

    return [dep.strip() for dep in dependencies if '://' in dep]


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
    """
    allow network access during the build and set the %dist macro
    (we have to download packages from pypi)
    """
    options = [
        "config_opts['rpmbuild_networking'] = True",
        "config_opts['macros']['%dist'] = '.el7'",
    ]
    missing = []

    try:
        makedirs(expanduser('~/.config'))
    except OSError as e:
        if e.errno != EEXIST:
            raise

    with open(expanduser('~/.config/mock.cfg'), 'a+') as f:
        f.seek(0)
        config_lines = f.readlines()

        for line in options:
            line = line + '\n'
            if line not in config_lines:
                missing += [line]

        if missing:
            f.write('\n\n# Added by cloudify build_rpm.py\n')

            logger.info('configuring missing options: %s', missing)
            f.writelines(missing)


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
    """
    Extract RPM `Source*: ` definitions from the spec file
    so we can download them
    """
    sources = []
    with open(spec_file) as f:
        for line in f:
            key, sep, value = line.strip().partition(':')
            if sep and key.strip().lower().startswith('source'):
                sources.append(value.strip())

    return sources


if __name__ == "__main__":
    main(sys.argv[1:])

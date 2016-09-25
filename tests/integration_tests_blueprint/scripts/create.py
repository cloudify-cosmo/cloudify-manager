#!/usr/bin/env python
import os
from os.path import join, dirname

from cloudify import ctx
ctx.download_resource(
        join('scripts', 'utils.py'),
        join(dirname(__file__), 'utils.py'))
import utils  # noqa

SYSTEM_LEVEL_DEPENDENCIES = ['git',
                             'python-pip',
                             'python-dev',
                             'build-essential',
                             'bridge-utils',
                             's3cmd']

CLOUDIFY_PACKAGES = ctx.node.properties['cloudify_packages']

MANAGER_BP_BRANCH = ctx.node.properties['cloudify_manager_blueprints_branch']
MANAGER_BP_ORG = ctx.node.properties['cloudify_manager_blueprints_org']

MANAGER_BLUEPRINTS_REPO = {
    'package_name': 'cloudify-manager-blueprints',
    'branch': MANAGER_BP_BRANCH,
    'org': MANAGER_BP_ORG}

PYTHON_DEPENDENCIES = [('nose', '1.3.7'),
                       ('python-dateutil', '2.5.3'),
                       # Jinja is installed in a newer version
                       # but cfy requires v2.7.2
                       ('jinja2', '2.7.2'),
                       ('requests', '2.7.0')]


def print_packages_config(packages):
    column_width = 40
    out = '{0}{1}{2}{3}{0}'.format(os.linesep,
                                   'Package Name'.ljust(column_width),
                                   'Package Branch'.ljust(column_width),
                                   'Organization'.ljust(column_width))
    for package in packages:
        out = out + package['package_name'].ljust(column_width)
        out = out + package['branch'].ljust(column_width)
        out = out + package['org'].ljust(column_width)
        out = out + os.linesep
    ctx.logger.info(out)


def install_system_level_deps():
    ctx.logger.info('Installing the required system level dependencies...')
    utils.sudo('apt-get update')
    utils.install_sys_level(SYSTEM_LEVEL_DEPENDENCIES)
    utils.install_pip()
    utils.install_venv()


def install_cloudify_packages():
    utils.create_cloudify_venv()
    ctx.logger.info('Installing cloudify packages...')
    for package in CLOUDIFY_PACKAGES:
        package_path = utils.clone(package_name=package['package_name'],
                                   branch=package['branch'],
                                   org=package['org'])
        if package['package_name'] == 'cloudify-manager':
            utils.pip_install_manager_deps(package_path)
        else:
            utils.pip_install(package_name=package['package_name'],
                              package_path=package_path)

    for package, version in PYTHON_DEPENDENCIES:
        utils.pip_install(package_name=package,
                          version=version)


def create_key_file(key_name='p_key.pem'):
    key_path = os.path.join(utils.WORKDIR, '.ssh', key_name)
    if not os.path.isfile(key_path):
        utils.run(command='ssh-keygen -t rsa -N "" -f {0}'.format('p_key.pem'),
                  workdir=os.path.join(utils.WORKDIR, '.ssh'))
    return key_path


def run_docl_bootstrap_or_download():
    ctx.logger.info('Preparing docl bootstrap execution')
    docl_script_path = join(utils.WORKDIR, 'docl_init.sh')
    ctx.download_resource(join('scripts', 'docl_init.sh'), docl_script_path)
    utils.run('chmod +x {0}'.format(docl_script_path))

    ctx.logger.info('Cloning cloudify manager blueprints {0}'
                    .format(MANAGER_BLUEPRINTS_REPO))
    repo_path = utils.clone(**MANAGER_BLUEPRINTS_REPO)

    simple_bp_path = os.path.join(repo_path,
                                  'simple-manager-blueprint.yaml')
    ctx.logger.info('Creating private key file')
    private_key_path = create_key_file()

    rebuild = ctx.node.properties['rebuild']
    if MANAGER_BP_BRANCH != 'master':
        rebuild = 'true'
    utils.run('{0} {1} {2} {3} {4} {5}'
              .format(docl_script_path,
                      utils.CLOUDIFY_VENV_PATH,
                      simple_bp_path,
                      private_key_path,
                      utils.REPOS_DIR,
                      rebuild),
              out=True)


def install_docker():
    ctx.logger.info('Installing the latest version of docker...')
    script_name = 'get_docker.sh'
    utils.run('curl -o {0} https://get.docker.com/'.format(script_name),
              workdir=utils.WORKDIR)
    utils.run('chmod +x {0}'.format(script_name), workdir=utils.WORKDIR)
    utils.sudo('bash {0}'.format(script_name), workdir=utils.WORKDIR)

    utils.sudo('usermod -aG docker {0}'
               .format(ctx.node.properties['ssh_user']))
    utils.sudo('service docker stop')
    _create_cloudify_bridge()
    utils.sudo("sed -i '$ a DOCKER_OPTS=\"--bridge cfy0 "
               "--host 172.20.0.1\"' /etc/default/docker")
    utils.sudo('service docker start')


def _create_cloudify_bridge():
    proc, stdout, stderr = utils.sudo('brctl show')
    if 'cfy0' not in stdout:
        ctx.logger.info('creating cfy0 network bridge...')
        utils.sudo('brctl addbr cfy0')
        utils.sudo('ip addr add 172.20.0.1/24 dev cfy0')
        utils.sudo('ip link set dev cfy0 up')


def main():
    print_packages_config(CLOUDIFY_PACKAGES)
    # install all of the required system level dependencies
    install_system_level_deps()
    # install all of the required cloudify python packages
    install_cloudify_packages()
    install_docker()
    # Run the docl_init.sh script
    run_docl_bootstrap_or_download()


main()

#/*******************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# *******************************************************************************/

import logging

__author__ = 'elip'

import os
from os import path
import json

from celery.utils.log import get_task_logger
from celery import task
from fabric.api import hide
from cosmo_fabric.runner import FabricRetryingRunner

COSMO_APP_NAME = "cosmo"

COSMO_CELERY_URL = "https://github.com/CloudifySource/cosmo-celery-common/archive/master.zip"

PLUGIN_INSTALLER_NAME = "cosmo-plugin-plugin-installer"
PLUGIN_INSTALLER_URL = "https://github.com/CloudifySource/cosmo-plugin-plugin-installer/archive/develop.zip"

COSMO_PLUGIN_NAMESPACE = ["cloudify", "tosca", "artifacts", "plugin"]

logger = get_task_logger(__name__)
logger.level = logging.DEBUG


@task
def install(worker_config, __cloudify_id, cloudify_runtime, local=False, **kwargs):

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    _install_latest_pip(runner, __cloudify_id)
    _install_celery(runner, worker_config, __cloudify_id)

@task
def start(worker_config, cloudify_runtime, local=False, **kwargs):

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    # change owner again since more directories were added
    runner.sudo("chown -R {0}:{0} {1}".format(worker_config['user'], worker_config['app_dir']))

    logger.info("starting celery worker")
    runner.sudo("service celeryd start")

    logger.debug(runner.get("/var/log/celery/celery.log"))

    _verify_no_celery_error(runner, worker_config)

    runner.run("celery inspect registered --broker={0}".format(worker_config['broker']))


@task
def restart(worker_config, cloudify_runtime, local=False, **kwargs):

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    restart_celery_worker(runner, worker_config)
    # fabric raises SystemExit on failure, so we transform this to a regular exception.


def create_runner(local, host_string, key_filename):
    runner = FabricRetryingRunner(
        local=local,
        host_string=host_string,
        key_filename=key_filename)
    return runner


def _install_latest_pip(runner, node_id):
    logger.info("installing latest pip installation [node_id=%s]", node_id)
    logger.debug("retrieving pip script [node_id=%s]", node_id)
    runner.sudo("wget https://raw.github.com/pypa/pip/master/contrib/get-pip.py")
    logger.debug("installing setuptools [node_id=%s]", node_id)
    runner.sudo("apt-get -q -y install python-pip")
    logger.debug("building pip installation [node_id=%s]", node_id)
    runner.sudo("python get-pip.py")


def prepare_configuration(worker_config, cloudify_runtime):
    ip = get_machine_ip(cloudify_runtime)
    worker_config['host'] = ip
    worker_config['home'] = "/home/" + worker_config['user']
    worker_config['app_dir'] = worker_config['home'] + "/" + COSMO_APP_NAME


def restart_celery_worker(runner, worker_config):
    runner.sudo('service celeryd restart')
    _verify_no_celery_error(runner, worker_config)


def _verify_no_celery_error(runner, worker_config):

    user = worker_config['user']
    home = "/home/" + user
    celery_error_out = '{0}/celery_error.out'.format(home)

    output = None
    with hide('aborts', 'running', 'stdout', 'stderr'):
        try:
            output = runner.get(celery_error_out)
        except BaseException:
            pass

    if output:

        # this means the celery worker had an uncaught exception and it wrote its content
        # to the file above because of our custom exception handler (see celery.py)

        runner.run('rm {0}'.format(celery_error_out))
        raise RuntimeError('Celery worker failed to start:\n{0}'.format(output))


def _install_celery(runner, worker_config, node_id):

    cosmo_properties = {
        'management_ip': worker_config['management_ip'],
        'ip': worker_config['host']
    }
    user = worker_config['user']
    broker_url = worker_config['broker']
    app_dir = worker_config['app_dir']
    home = worker_config['home']

    runner.sudo("rm -rf " + app_dir)

    # this will also install celery because of transitive dependencies
    install_celery_plugin_to_dir(runner, home, COSMO_CELERY_URL)

    # since sudo pip created the app dir. the owner is root. but actually it is used by celery.
    runner.sudo("chown -R {0} {1}".format(user, app_dir))

    # write cosmo properties
    logger.debug("writing cosmo properties file [node_id=%s]: %s", node_id, cosmo_properties)
    cosmo_properties_path = path.join(app_dir, "cosmo.txt")
    runner.put(json.dumps(cosmo_properties), cosmo_properties_path, use_sudo=True)

    plugin_installer_installation_path = create_namespace_path(runner, COSMO_PLUGIN_NAMESPACE, app_dir)

    # install the plugin installer
    install_celery_plugin_to_dir(runner, plugin_installer_installation_path, PLUGIN_INSTALLER_URL)

    # daemonize
    runner.sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    runner.sudo("chmod +x /etc/init.d/celeryd")
    env = None
    if 'env' in worker_config:
        env = worker_config['env']
    config_file = build_celeryd_config(user, home, COSMO_APP_NAME, node_id, broker_url, env)
    runner.put(config_file, "/etc/default/celeryd", use_sudo=True)


def install_celery_plugin_to_dir(runner, to_dir, plugin_url):

    # this will install the package and the dependencies into the python installation
    runner.sudo("pip install {0}".format(plugin_url))

    # install the package to the target directory. this should also remove the plugin package from the python
    # installation.
    runner.sudo("pip install --no-deps -t {0} {1}".format(to_dir, plugin_url))


def create_namespace_path(runner, namespace_parts, base_dir):
    """
    Creates the namespaces path the plugin directory will reside in.
    For example
        input : cloudify.tosca.artifacts.plugin.python_webserver_installer
        output : a directory path app/cloudify/tosca/artifacts/plugin
    "app/cloudify/plugins/host_provisioner". In addition, "__init.py__" files will be created in each of the
    path's sub directories.

    """

    logger.info("creating namespace path : {0} in directory {1}".format(namespace_parts, base_dir))

    runner.run("mkdir -p " + base_dir)
    remote_plugin_path = base_dir
    for folder in namespace_parts:
        remote_plugin_path = os.path.join(remote_plugin_path, folder)
        runner.run("mkdir -p " + remote_plugin_path)
        runner.run('echo "" > ' + remote_plugin_path + '/__init__.py')

    return remote_plugin_path


def get_machine_ip(cloudify_runtime):
    if not cloudify_runtime:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')

    for value in cloudify_runtime.values():
        if 'ip' in value:
            return value['ip']

    raise ValueError('cannot get machine ip - cloudify_runtime format error')


def build_env_string(env):

    string = ""
    for key, value in env.iteritems():
        string = "export {0}=\"{1}\"\n{2}".format(key, value, string)
    return string


def build_celeryd_config(user, workdir, app, node_id, broker_url, env=None):

    if not env:
        env = {}
    env_string = build_env_string(env)

    return '''
%(env)s
CELERYD_USER="%(user)s"
CELERYD_GROUP="%(user)s"
CELERY_TASK_SERIALIZER="json"
CELERY_RESULT_SERIALIZER="json"
CELERY_RESULT_BACKEND="%(broker_url)s"
CELERYD_CHDIR="%(workdir)s"
CELERYD_OPTS="\
--events \
--loglevel=debug \
--app=%(app)s \
-Q %(node_id)s \
--broker=%(broker_url)s \
--hostname=%(node_id)s"
''' % dict(env=env_string,
           user=user,
           workdir=workdir,
           app=app,
           node_id=node_id,
           broker_url=broker_url)
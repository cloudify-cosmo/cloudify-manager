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

from os.path import expanduser
from celery.utils.log import get_task_logger
from celery import task
from cosmo_fabric.runner import FabricRetryingRunner
from versions import PLUGIN_INSTALLER_VERSION, COSMO_CELERY_COMMON_VERSION, KV_STORE_VERSION
from cosmo.constants import VIRTUALENV_PATH_KEY, COSMO_APP_NAME, COSMO_PLUGIN_NAMESPACE


COSMO_CELERY_URL = "https://github.com/CloudifySource/cosmo-celery-common/archive/{0}.zip"\
                   .format(COSMO_CELERY_COMMON_VERSION)

PLUGIN_INSTALLER_URL = "https://github.com/CloudifySource/cosmo-plugin-plugin-installer/archive/{0}.zip"\
                       .format(PLUGIN_INSTALLER_VERSION)

KV_STORE_URL = "https://github.com/CloudifySource/cosmo-plugin-kv-store/archive/{0}.zip" \
    .format(KV_STORE_VERSION)


logger = get_task_logger(__name__)
logger.level = logging.DEBUG

MANAGEMENT_IP = "MANAGEMENT_IP"
AGENT_IP = "AGENT_IP"
BROKER_URL = "BROKER_URL"


@task
def install(worker_config, __cloudify_id, cloudify_runtime, virtualenv=True, local=False, **kwargs):

    logger.info("installing worker. virtualenv = {0}".format(virtualenv))

    prepare_configuration(worker_config, cloudify_runtime)
    worker_config['virtualenv'] = virtualenv

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    _install_latest_pip(runner, __cloudify_id)

    if is_virtualenv(worker_config):
        logger.info("creating virtualenv for worker process")
        # create virtual env for the worker
        _install_virtualenv(runner, __cloudify_id)
        _create_virtualenv(runner, get_virtual_env_path(worker_config), __cloudify_id)

    _install_celery(runner, worker_config, __cloudify_id)


@task
def start(worker_config, cloudify_runtime, local=False, **kwargs):

    logger.info("starting celery worker")

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    # change owner again since more directories were added
    runner.sudo("chown -R {0}:{0} {1}".format(worker_config['user'], worker_config['app_dir']))

    runner.sudo("service celeryd start")

    logger.debug(runner.get("/var/log/celery/celery.log"))

    _verify_no_celery_error(runner, worker_config)


@task
def restart(worker_config, cloudify_runtime, local=False, **kwargs):

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    restart_celery_worker(runner, worker_config)


def _install_virtualenv(runner, __cloudify_id):

    logger.debug("installing virtualenv [node_id=%s]", __cloudify_id)
    runner.sudo("pip install virtualenv")


def _create_virtualenv(runner, env_path, __cloudify_id):
    logger.debug("creating virtualenv [node_id=%s]", __cloudify_id)
    runner.sudo("virtualenv {0}".format(env_path))


def create_runner(local, host_string, key_filename):
    runner = FabricRetryingRunner(
        local=local,
        host_string=host_string,
        key_filename=key_filename)
    return runner


def _install_latest_pip(runner, node_id):
    logger.info("installing latest pip installation [node_id=%s]", node_id)
    logger.debug("retrieving pip script [node_id=%s]", node_id)
    runner.sudo("wget -N https://raw.github.com/pypa/pip/master/contrib/get-pip.py")
    logger.debug("installing setuptools [node_id=%s]", node_id)

    #checking whether to install pip using yum or apt-get
    package_installer = "yum" if len(runner.run("whereis yum")[4:].strip()) > 0 else "apt-get"
    logger.debug("installing pip using {0}".format(package_installer))
    runner.sudo("{0} -q -y install python-pip".format(package_installer))
    logger.debug("upgrading setuptools [node_id=%s]", node_id)
    runner.sudo('pip install --upgrade setuptools')

    logger.debug("building pip installation [node_id=%s]", node_id)
    runner.sudo("python get-pip.py")


def prepare_configuration(worker_config, cloudify_runtime):
    ip = get_machine_ip(cloudify_runtime)
    worker_config['host'] = ip
    #root user has no "/home/" prepended to its home directory
    worker_config['home'] = "/home/" + worker_config['user'] if worker_config['user'] != 'root' else '/root'
    worker_config['app_dir'] = worker_config['home'] + "/" + COSMO_APP_NAME

    if "env" not in worker_config:
        worker_config['env'] = dict()

    if MANAGEMENT_IP not in worker_config["env"]:
        if MANAGEMENT_IP not in os.environ:
            raise RuntimeError("{0} is not present in worker_config.env nor environment".format(MANAGEMENT_IP))
        worker_config["env"][MANAGEMENT_IP] = os.environ[MANAGEMENT_IP]
    worker_config["env"][AGENT_IP] = ip


def restart_celery_worker(runner, worker_config):
    runner.sudo('service celeryd restart')
    _verify_no_celery_error(runner, worker_config)


def _verify_no_celery_error(runner, worker_config):

    user = worker_config['user']
    home = "/home/" + user if user != 'root' else '/root'
    celery_error_out = '{0}/celery_error.out'.format(home)

    # this means the celery worker had an uncaught exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.run('rm {0}'.format(celery_error_out))
        raise RuntimeError('Celery worker failed to start:\n{0}'.format(output))


def _install_celery(runner, worker_config, node_id):

    user = worker_config['user']
    app_dir = worker_config['app_dir']
    home = worker_config['home']

    runner.sudo("rm -rf " + app_dir)

    # this will also install celery because of transitive dependencies
    install_celery_plugin_to_dir(runner, worker_config, home, COSMO_CELERY_URL)

    # since sudo pip created the app dir. the owner is root. but actually it is used by celery.
    runner.sudo("chown -R {0} {1}".format(user, app_dir))

    # copy celery.py file to app dir
    from cloudify import celery
    module_file = celery.__file__
    runner.run('cp {0} {1}'.format(module_file, app_dir))

    plugins_installation_path = create_namespace_path(runner, COSMO_PLUGIN_NAMESPACE, app_dir)

    # install the plugin installer
    install_celery_plugin_to_dir(runner, worker_config, plugins_installation_path, PLUGIN_INSTALLER_URL)

    # install the kv store
    install_celery_plugin_to_dir(runner, worker_config, plugins_installation_path, KV_STORE_URL)

    # daemonize
    runner.sudo("wget -N https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    runner.sudo("chmod +x /etc/init.d/celeryd")
    config_file = build_celeryd_config(worker_config, node_id)
    runner.put(config_file, "/etc/default/celeryd", use_sudo=True)


def install_celery_plugin_to_dir(runner, worker_config, to_dir, plugin_url):

    # this will install the package and the dependencies into the python installation
    runner.sudo("{0} install {1}".format(get_pip(worker_config), plugin_url))

    # install the package to the target directory. this should also remove the plugin package from the python
    # installation.
    runner.sudo("{0} install --no-deps -t {1} {2}".format(get_pip(worker_config), to_dir, plugin_url))


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


def get_pip(worker_config):
    return get_prefix_for_command(worker_config, "pip")


def get_celery(worker_config):
    return get_prefix_for_command(worker_config, "celery")


def get_celeryd_multi(worker_config):
    return get_prefix_for_command(worker_config, "celeryd-multi")


def get_prefix_for_command(worker_config, command):
    try:
        return os.path.join(get_virtual_env_path(worker_config), "bin", command)
    except KeyError:
        return command


def is_virtualenv(worker_config):
    try:
        get_virtual_env_path(worker_config)
        return True
    except KeyError:
        return False


def get_virtual_env_path(worker_config):

    if 'virtualenv_path' in worker_config:
        # user has explicitly defined a virtualenv path
        return os.path.join(worker_config['virtualenv_path'])
    elif worker_config['virtualenv']:
        # user has indicated that he wishes to use virtualenv, but no path was defined.
        # use the default path
        return os.path.join(worker_config['home'], "ENV")

    raise KeyError("No virtualenv configuration was made in worker {0}".format(worker_config))


def build_env_string(env):

    string = ""
    for key, value in env.iteritems():
        string = "export {0}=\"{1}\"\n{2}".format(key, value, string)
    return string


def get_broker_url(worker_config):
    """
    Gets the broker URL from either os.environ or worker_config[env].
    Raises a RuntimeError if neither exist.
    """
    if BROKER_URL in os.environ:
        return os.environ[BROKER_URL]
    elif "env" in worker_config and BROKER_URL in worker_config["env"]:
        return worker_config["env"][BROKER_URL]
    raise RuntimeError(
        "Broker URL cannot be set - {0} doesn't exist in os.environ nor worker_config.env".format(BROKER_URL))


def build_celeryd_config(worker_config, node_id):

    user = worker_config['user']
    broker_url = get_broker_url(worker_config)
    workdir = worker_config['home']

    env = {}
    if 'env' in worker_config:
        env = worker_config['env']

    if is_virtualenv(worker_config):
        # put virtualenv prefix so that other plugins will have it in their env.
        env[VIRTUALENV_PATH_KEY] = get_virtual_env_path(worker_config)

    env_string = build_env_string(env)

    return '''
%(env)s
CELERYD_MULTI="%(celeryd_multi)s"
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
           celeryd_multi=get_celeryd_multi(worker_config),
           user=user,
           workdir=workdir,
           app=COSMO_APP_NAME,
           node_id=node_id,
           broker_url=broker_url)
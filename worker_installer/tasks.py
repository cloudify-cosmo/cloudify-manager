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

from celery.utils.log import get_task_logger
from celery import task
from cosmo_fabric.runner import FabricRetryingRunner
from versions import PLUGIN_INSTALLER_VERSION, COSMO_CELERY_COMMON_VERSION, KV_STORE_VERSION
from cloudify.constants import COSMO_APP_NAME, CLOUDIFY_APP_DIR_KEY, VIRTUALENV_PATH_KEY, BUILT_IN_AGENT_PLUGINS


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
def install(worker_config, __cloudify_id, cloudify_runtime, local=False, **kwargs):

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    _install_latest_pip(runner, __cloudify_id)

    logger.info("installing worker. virtualenv = {0}".format(worker_config['virtualenv_path']))

    _create_virtualenv(runner, worker_config['virtualenv_path'], __cloudify_id)
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

    runner.sudo("service celeryd start")

    logger.debug(runner.get("{0}/log/celery/celery.log".format(worker_config['app_dir'])))

    _verify_no_celery_error(runner)


@task
def restart(worker_config, cloudify_runtime, local=False, **kwargs):

    prepare_configuration(worker_config, cloudify_runtime)

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    restart_celery_worker(runner)


def create_runner(local, host_string, key_filename):
    runner = FabricRetryingRunner(
        local=local,
        host_string=host_string,
        key_filename=key_filename)
    return runner


def _install_latest_pip(runner, node_id):
    logger.info("installing latest pip installation [node_id=%s]", node_id)
    runner.run("wget -N https://raw2.github.com/pypa/pip/1.5/contrib/get-pip.py")

    package_installer = "yum" if len(runner.run("whereis yum")[4:].strip()) > 0 else "apt-get"
    logger.debug("installing setuptools using {0}".format(package_installer))
    runner.sudo("{0} -y install python-setuptools".format(package_installer))

    runner.sudo("python get-pip.py")


def prepare_configuration(worker_config, cloudify_runtime):
    ip = get_machine_ip(cloudify_runtime)
    worker_config['host'] = ip
    #root user has no "/home/" prepended to its home directory
    worker_config['home'] = "/home/" + worker_config['user'] if worker_config['user'] != 'root' else '/root'
    worker_config['app_dir'] = worker_config['home'] + "/celery"

    if "env" not in worker_config:
        worker_config['env'] = dict()
    if "virtualenv_path" not in worker_config:
        worker_config['virtualenv_path'] = worker_config['app_dir'] + "/ENV"

    if MANAGEMENT_IP not in worker_config["env"]:
        if MANAGEMENT_IP not in os.environ:
            raise RuntimeError("{0} is not present in worker_config.env nor environment".format(MANAGEMENT_IP))
        worker_config["env"][MANAGEMENT_IP] = os.environ[MANAGEMENT_IP]
    worker_config["env"][AGENT_IP] = ip


def restart_celery_worker(runner):
    runner.sudo('service celeryd restart')
    _verify_no_celery_error(runner)


def _verify_no_celery_error(runner):

    celery_error_out = os.path.expanduser('~/celery_error.out')

    # this means the celery worker had an uncaught exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.run('rm {0}'.format(celery_error_out))
        raise RuntimeError('Celery worker failed to start:\n{0}'.format(output))


def _install_celery(runner, worker_config, node_id):

    app_dir = worker_config['app_dir']

    # this will also install celery because of transitive dependencies
    install_celery_plugin(runner, worker_config, COSMO_CELERY_URL)

    # install the plugin installer
    install_celery_plugin(runner, worker_config, PLUGIN_INSTALLER_URL)

    # install the kv store
    install_celery_plugin(runner, worker_config, KV_STORE_URL)

    # daemonize
    runner.sudo("wget -N https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    runner.sudo("chmod +x /etc/init.d/celeryd")
    config_file = build_celeryd_config(worker_config, node_id, app_dir)
    runner.put(config_file, "/etc/default/celeryd", use_sudo=True)


def install_celery_plugin(runner, worker_config, plugin_url):

    # this will install the package and the dependencies into the python installation
    runner.run("{0} install --process-dependency-links {1}".format(get_pip(worker_config), plugin_url))


def get_machine_ip(cloudify_runtime):
    if not cloudify_runtime:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')

    for value in cloudify_runtime.values():
        if 'ip' in value:
            return value['ip']

    raise ValueError('cannot get machine ip - cloudify_runtime format error')


def get_pip(worker_config):
    return get_prefix_for_command(worker_config['virtualenv_path'], "pip")


def get_celery(worker_config):
    return get_prefix_for_command(worker_config['virtualenv_path'], "celery")


def get_celeryd_multi(worker_config):
    return get_prefix_for_command(worker_config['virtualenv_path'], "celeryd-multi")


def get_prefix_for_command(virtualenv_path, command):
    return os.path.join(virtualenv_path, "bin", command)


def build_env_string(env):

    string = ""
    for key, value in env.iteritems():
        string = "export {0}=\"{1}\"\n{2}".format(key, value, string)
    return string


def _create_virtualenv(runner, env_path, __cloudify_id):
    logger.debug("installing virtualenv [node_id=%s]", __cloudify_id)
    runner.sudo("pip install virtualenv")
    logger.debug("creating virtualenv [node_id=%s]", __cloudify_id)
    runner.run("virtualenv {0}".format(env_path))
    runner.run("{0}/bin/pip --version".format(env_path))
    logger.info("upgrading pip installation within virtualenv")
    runner.run("{0}/bin/pip install --upgrade pip".format(env_path))
    runner.run("{0}/bin/pip --version".format(env_path))


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


def build_celeryd_config(worker_config, node_id, app_dir):

    user = worker_config['user']
    broker_url = get_broker_url(worker_config)
    virtualenv_path = worker_config['virtualenv_path']

    env = {}
    if 'env' in worker_config:
        env = worker_config['env']

    env[VIRTUALENV_PATH_KEY] = virtualenv_path
    env[CLOUDIFY_APP_DIR_KEY] = app_dir

    env_string = build_env_string(env)

    return '''
%(env)s
CELERYD_MULTI="%(celeryd_multi)s"
CELERYD_USER="%(user)s"
CELERYD_GROUP="%(user)s"
CELERY_TASK_SERIALIZER="json"
CELERY_RESULT_SERIALIZER="json"
CELERY_RESULT_BACKEND="%(broker_url)s"
DEFAULT_PID_FILE="%(pid_file)s"
DEFAULT_LOG_FILE="%(log_file)s"
CELERYD_OPTS="\
--events \
--loglevel=debug \
--app=%(app)s \
--include=%(includes)s \
-Q %(node_id)s \
--broker=%(broker_url)s \
--hostname=%(node_id)s"
''' % dict(env=env_string,
           celeryd_multi=get_celeryd_multi(worker_config),
           user=user,
           pid_file="{0}/run/celery/%n.pid".format(app_dir),
           log_file="{0}/log/celery/%n.log".format(app_dir),
           includes=",".join(BUILT_IN_AGENT_PLUGINS),
           app=COSMO_APP_NAME,
           node_id=node_id,
           broker_url=broker_url)

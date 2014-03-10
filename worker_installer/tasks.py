#########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

__author__ = 'elip'

import os
from cloudify.decorators import operation
from cosmo_fabric.runner import FabricRetryingRunner
from versions import PLUGIN_INSTALLER_VERSION, COSMO_CELERY_COMMON_VERSION,\
    KV_STORE_VERSION, RIEMANN_CONFIGURER_VERSION, AGENT_INSTALLER_VERSION
from cloudify.constants import COSMO_APP_NAME, VIRTUALENV_PATH_KEY, \
    BUILT_IN_AGENT_PLUGINS, BUILT_IN_MANAGEMENT_PLUGINS, MANAGER_IP_KEY, \
    LOCAL_IP_KEY, CELERY_WORK_DIR_PATH_KEY, MANAGER_REST_PORT_KEY


COSMO_CELERY_URL = \
    "https://github.com/CloudifySource/cosmo-celery-common/archive/{0}.zip"\
    .format(COSMO_CELERY_COMMON_VERSION)

PLUGIN_INSTALLER_URL = "https://github.com/CloudifySource/cosmo-plugin-plugin"\
                       "-installer/archive/{0}.zip".format(
                           PLUGIN_INSTALLER_VERSION)

KV_STORE_URL = "https://github.com/CloudifySource/cosmo-plugin-kv-store/"\
               "archive/{0}.zip".format(KV_STORE_VERSION)

RIEMANN_CONFIGURER_URL = \
    "https://github.com/CloudifySource/cosmo-plugin-riemann-configurer/"\
    "archive/{0}.zip".format(RIEMANN_CONFIGURER_VERSION)

AGENT_INSTALLER_URL = \
    "https://github.com/CloudifySource/cosmo-plugin-agent-installer/"\
    "archive/{0}.zip".format(AGENT_INSTALLER_VERSION)


BROKER_URL = "BROKER_URL"


@operation
def install(ctx, worker_config, local=False, **kwargs):

    prepare_configuration(worker_config, ctx, local)

    ctx.logger.info(
        "installing celery worker {0}".format(worker_config["name"]))

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    _install_latest_pip(runner, worker_config)

    ctx.logger.info("installing worker. virtualenv = {0}".format(
        worker_config[VIRTUALENV_PATH_KEY]))

    _create_virtualenv(runner,
                       worker_config[VIRTUALENV_PATH_KEY],
                       worker_config["name"])
    _install_celery(runner, worker_config)


@operation
def uninstall(ctx, worker_config, local=False, **kwargs):

    prepare_configuration(worker_config, ctx)

    ctx.logger.info(
        "uninstalling celery worker {0}".format(worker_config["name"]))

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    files_to_delete = [
        "/etc/init.d/celeryd-{0}".format(worker_config["name"]),
        "/etc/default/celeryd-{0}".format(worker_config["name"]),
    ]
    folders_to_delete = [
        worker_config[VIRTUALENV_PATH_KEY],
        worker_config[CELERY_WORK_DIR_PATH_KEY]
    ]
    delete_files_if_exist(ctx, worker_config, runner, files_to_delete)
    delete_folders_if_exist(ctx, worker_config, runner, folders_to_delete)


def delete_files_if_exist(ctx, worker_config, runner, files):
    missing_files = []
    for file_to_delete in files:
        if runner.exists(file_to_delete):
            runner.sudo("rm {0}".format(file_to_delete))
        else:
            missing_files.append(file_to_delete)
    if missing_files:
        ctx.logger.debug(
            "Could not find files {0} while trying to uninstall worker {1}"
            .format(missing_files, worker_config["name"]))


def delete_folders_if_exist(ctx, worker_config, runner, folders):
    missing_folders = []
    for folder_to_delete in folders:
        if runner.exists(folder_to_delete):
            runner.sudo("rm -rf {0}".format(folder_to_delete))
        else:
            missing_folders.append(folder_to_delete)
    if missing_folders:
        ctx.logger.debug(
            "Could not find folders {0} while trying to uninstall worker {1}"
            .format(missing_folders, worker_config["name"]))


@operation
def stop(ctx, worker_config, local=False, **kwargs):

    prepare_configuration(worker_config, ctx)

    ctx.logger.info("stopping celery worker {0}".format(worker_config["name"]))

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    service_file_path = "/etc/init.d/celeryd-{0}".format(worker_config["name"])

    if runner.exists(service_file_path):
        runner.sudo("service celeryd-{0} stop".format(worker_config["name"]))
    else:
        ctx.logger.debug(
            "Could not find any workers with name {0}. nothing to do."
            .format(worker_config["name"]))


@operation
def start(ctx, worker_config, local=False, **kwargs):

    prepare_configuration(worker_config, ctx)

    ctx.logger.info("starting celery worker {0}".format(worker_config["name"]))

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    runner.sudo("service celeryd-{0} start".format(worker_config["name"]))

    ctx.logger.debug(runner.get(worker_config['log_file']))

    _verify_no_celery_error(runner, worker_config)


@operation
def restart(ctx, worker_config, local=False, **kwargs):

    prepare_configuration(worker_config, ctx)

    ctx.logger.info(
        "restarting celery worker {0}".format(worker_config["name"]))

    host_string = key_filename = None
    if not local:
        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

    runner = create_runner(local, host_string, key_filename)

    restart_celery_worker(runner, worker_config)


def create_runner(local, host_string, key_filename):
    runner = FabricRetryingRunner(
        local=local,
        host_string=host_string,
        key_filename=key_filename)
    return runner


def _install_latest_pip(runner, worker_config):
    runner.run(
        "wget https://raw2.github.com/pypa/pip/1.5/contrib/get-pip.py -O "
        "{0}/get-pip.py".format(worker_config['home']))

    runner.sudo("apt-get update -y")
    runner.sudo("apt-get install -f)
    runner.sudo("apt-get -y install python-setuptools")

    runner.sudo("python {0}/get-pip.py".format(worker_config['home']))


def prepare_configuration(worker_config, ctx, local=False):
    ip = None
    if ctx.node_id is not None and not local:
        ip = get_machine_ip(ctx)
        worker_config['host'] = ip

    if not ctx.node_id and "user" not in worker_config:
        # we are starting a worker dedicated for a deployment
        # (not specific node)
        # use the same user we used when bootstrapping
        if "MANAGEMENT_USER" in os.environ:
            worker_config["user"] = os.environ["MANAGEMENT_USER"]
        else:
            raise RuntimeError("Cannot determine user")

    # root user has no "/home/" prepended to its home directory
    # we cannot use expanduser('~') here since this code may run on
    #  a different machine than the one the worker is
    # being actually installed on
    worker_config['home'] = "/home/" + worker_config['user'] \
        if worker_config['user'] != 'root' else '/root'

    if "name" not in worker_config:
        worker_config["name"] = ctx.node_id

    if VIRTUALENV_PATH_KEY not in worker_config:
        worker_config[VIRTUALENV_PATH_KEY] = \
            worker_config['home'] + "/{0}__worker/env".format(
                worker_config["name"])

    if CELERY_WORK_DIR_PATH_KEY not in worker_config:
        worker_config[CELERY_WORK_DIR_PATH_KEY] = \
            worker_config['home'] + "/{0}__worker/work".format(
                worker_config["name"])

    if "env" not in worker_config:
        worker_config["env"] = {}

    if "management" not in worker_config:
        worker_config["management"] = False

    if "pid_file" not in worker_config:
        worker_config["pid_file"] = "{0}/{1}_worker.pid".format(
            worker_config[CELERY_WORK_DIR_PATH_KEY], worker_config["name"])

    if "log_file" not in worker_config:
        worker_config["log_file"] = \
            "{0}/{1}_worker.log".format(
                worker_config[CELERY_WORK_DIR_PATH_KEY], worker_config["name"])

    if MANAGER_IP_KEY not in worker_config["env"]:
        if MANAGER_IP_KEY not in os.environ:
            raise RuntimeError("{0} is not present in worker_config.env "
                               "nor environment".format(MANAGER_IP_KEY))
        worker_config["env"][MANAGER_IP_KEY] = os.environ[MANAGER_IP_KEY]
    worker_config["env"][LOCAL_IP_KEY] = ip


def restart_celery_worker(runner, worker_config):
    runner.sudo("service celeryd-{0} restart".format(worker_config["name"]))
    _verify_no_celery_error(runner, worker_config)


def _verify_no_celery_error(runner, worker_config):

    celery_error_out = os.path.join(
        worker_config[CELERY_WORK_DIR_PATH_KEY], 'celery_error.out')

    # this means the celery worker had an uncaught
    #  exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if runner.exists(celery_error_out):
        output = runner.get(celery_error_out)
        runner.run('rm {0}'.format(celery_error_out))
        raise RuntimeError(
            'Celery worker failed to start:\n{0}'.format(output))


def _install_celery(runner, worker_config):

    # this will also install celery because of transitive dependencies
    install_celery_plugin(runner, worker_config, COSMO_CELERY_URL)

    # install the plugin installer
    install_celery_plugin(runner, worker_config, PLUGIN_INSTALLER_URL)

    # install the kv store
    install_celery_plugin(runner, worker_config, KV_STORE_URL)

    if _is_management_node(worker_config):

            # install the agent installer
            install_celery_plugin(runner, worker_config, AGENT_INSTALLER_URL)

            # install the agent installer
            install_celery_plugin(runner,
                                  worker_config,
                                  RIEMANN_CONFIGURER_URL)

    # daemonize
    runner.sudo("wget -N https://raw.github.com/celery/celery/3.0/extra/"
                "generic-init.d/celeryd -O /etc/init.d/celeryd-{0}"
                .format(worker_config["name"]))
    runner.sudo("chmod +x /etc/init.d/celeryd-{0}".format(
        worker_config["name"]))
    config_file = build_celeryd_config(worker_config)
    runner.put(config_file, "/etc/default/celeryd-{0}".format(
        worker_config["name"]), use_sudo=True)

    # append the path to config file to the init script
    # (hack, but works for now)
    runner.sudo("sed -i '1 iCELERY_DEFAULTS=/etc/default/celeryd-{0}' "
                "/etc/init.d/celeryd-{0}".format(worker_config["name"]))

    # expose celery work directory
    runner.sudo("sed -i '1 iexport {0}={1}' /etc/init.d/celeryd-{2}"
                .format(CELERY_WORK_DIR_PATH_KEY,
                        worker_config[CELERY_WORK_DIR_PATH_KEY],
                        worker_config["name"]))

    # build initial includes
    if _is_management_node(worker_config):
        includes_list = BUILT_IN_MANAGEMENT_PLUGINS
    else:
        includes_list = BUILT_IN_AGENT_PLUGINS

    runner.put("INCLUDES={0}\n".format(",".join(includes_list)),
               "{0}/celeryd-includes".format(
                   worker_config[CELERY_WORK_DIR_PATH_KEY]), use_sudo=False)


def _is_management_node(worker_config):
    return worker_config["management"]


def install_celery_plugin(runner, worker_config, plugin_url):
    """
    This will install the package and the dependencies
    into the python installation
    """
    runner.run("{0} install --process-dependency-links {1}".format(
        get_pip(worker_config), plugin_url))


def get_machine_ip(ctx):
    if not ctx:
        raise ValueError('cannot get machine ip - ctx is not set')

    if 'ip' not in ctx:
        raise ValueError(
            'ip property is not set for node: {0}. This is mandatory'
            ' for installing agent via ssh.'.format(ctx.node_id))

    return ctx['ip']


def get_pip(worker_config):
    return get_prefix_for_command(worker_config[VIRTUALENV_PATH_KEY], "pip")


def get_celery(worker_config):
    return get_prefix_for_command(worker_config[VIRTUALENV_PATH_KEY], "celery")


def get_celeryd_multi(worker_config):
    return get_prefix_for_command(
        worker_config[VIRTUALENV_PATH_KEY],
        "celeryd-multi")


def get_prefix_for_command(virtualenv_path, command):
    return os.path.join(virtualenv_path, "bin", command)


def build_env_string(env):

    string = ""
    for key, value in env.iteritems():
        string = "export {0}=\"{1}\"\n{2}".format(key, value, string)
    return string


def _create_virtualenv(runner, env_path, name):
    runner.sudo("pip install virtualenv")
    runner.run("virtualenv {0}".format(env_path))
    runner.run("{0}/bin/pip install --upgrade pip".format(env_path))


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
        "Broker URL cannot be set - {0} doesn't exist in os.environ "
        "nor worker_config.env".format(BROKER_URL))


def get_manager_rest_port(worker_config):
    """
    Gets the broker URL from either os.environ or worker_config[env].
    Raises a RuntimeError if neither exist.
    """
    if MANAGER_REST_PORT_KEY in os.environ:
        return os.environ[MANAGER_REST_PORT_KEY]
    elif "env" in worker_config and MANAGER_REST_PORT_KEY \
            in worker_config["env"]:
        return worker_config["env"][MANAGER_REST_PORT_KEY]
    raise RuntimeError(
        "Manager rest port cannot be set - {0} doesn't exist in "
        "os.environ nor worker_config.env".format(MANAGER_REST_PORT_KEY))


def build_celeryd_config(worker_config):

    user = worker_config['user']
    broker_url = get_broker_url(worker_config)
    manager_rest_port = get_manager_rest_port(worker_config)

    env = {}
    if 'env' in worker_config:
        env = worker_config['env']

    env[VIRTUALENV_PATH_KEY] = worker_config[VIRTUALENV_PATH_KEY]
    env[CELERY_WORK_DIR_PATH_KEY] = worker_config[CELERY_WORK_DIR_PATH_KEY]
    env["IS_MANAGEMENT_NODE"] = worker_config["management"]
    env[BROKER_URL] = broker_url
    env[MANAGER_REST_PORT_KEY] = manager_rest_port

    # if this is the management worker, we know the user it uses
    if _is_management_node(worker_config):
        env["MANAGEMENT_USER"] = worker_config["user"]

    env_string = build_env_string(env)

    return '''
. %(celeryd_includes)s
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
--include=$INCLUDES \
-Q %(name)s \
--broker=%(broker_url)s \
--hostname=%(name)s"
''' % dict(celeryd_includes="{0}/celeryd-includes".format(
        worker_config[CELERY_WORK_DIR_PATH_KEY]),
        env=env_string,
        celeryd_multi=get_celeryd_multi(worker_config),
        user=user,
        pid_file=worker_config['pid_file'],
        log_file=worker_config['log_file'],
        app=COSMO_APP_NAME,
        name=worker_config["name"],
        broker_url=broker_url)

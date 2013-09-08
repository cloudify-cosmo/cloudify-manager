import os

__author__ = 'elip'

from StringIO import StringIO
from fabric.operations import local as lrun
from os import path
import time
import sys
import json

from celery.utils.log import get_task_logger
from celery import task
from fabric.api import settings, sudo, run, put, hide, get


COSMO_CELERY_URL = "https://github.com/iliapolo/cosmo-worker-utils/archive/master.zip"
PLUGIN_INSTALLER_URL = 'https://github.com/CloudifySource/' \
                       'cosmo-plugin-installer/archive/feature/CLOUDIFY-2022-initial-commit.zip'
COSMO_PLUGIN_NAMESPACE = ["cloudify", "tosca", "artifacts", "plugin"]

logger = get_task_logger(__name__)


@task
def install(worker_config, __cloudify_id, cloudify_runtime, local=False, **kwargs):
    try:
        prepare_configuration(worker_config, cloudify_runtime)

        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

        runner = create_runner(local, host_string, key_filename)

        install_latest_pip(runner, __cloudify_id)
        install_celery_worker(runner, worker_config, __cloudify_id)
    # fabric raises SystemExit on failure, so we transform this to a regular exception.
    except SystemExit, e:
        trace = sys.exc_info()[2]
        raise RuntimeError('Failed celery worker installation: {0}'.format(e)), None, trace


@task
def restart(worker_config, cloudify_runtime, local=False, **kwargs):
    try:
        prepare_configuration(worker_config, cloudify_runtime)

        host_string = '%(user)s@%(host)s:%(port)s' % worker_config
        key_filename = worker_config['key']

        runner = create_runner(local, host_string, key_filename)

        restart_celery_worker(runner, worker_config)
    # fabric raises SystemExit on failure, so we transform this to a regular exception.
    except SystemExit, e:
        trace = sys.exc_info()[2]
        raise RuntimeError('Failed celery worker restart: {0}'.format(e)), None, trace


def create_runner(local, host_string, key_filename):
    runner = FabricRetryingRunner(
        local=local,
        host_string=host_string,
        key_filename=key_filename)
    return runner


def install_latest_pip(runner, node_id):
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
    worker_config['app'] = 'cosmo'


def install_celery_worker(runner, worker_config, node_id):
    _install_celery(runner, worker_config, node_id)
    _verify_no_celery_error(runner, worker_config)


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
            runner.get(celery_error_out)
        except BaseException:
            pass

    # this means the celery worker had an uncaught exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if output:
        runner.run('rm {0}'.format(celery_error_out))
        error_content = output.getvalue()
        raise RuntimeError('Celery worker failed to start:\n{0}'.format(error_content))


def _install_celery(runner, worker_config, node_id):

    cosmo_properties = {
        'management_ip': worker_config['management_ip'],
        'ip': worker_config['host']
    }
    user = worker_config['user']
    broker_url = worker_config['broker']
    app = worker_config['app']
    home = "/home/" + user
    app_dir = home + "/" + app

    runner.sudo("rm -rf " + app_dir)

    # this will install celery because of transitive dependencies
    runner.sudo("pip install {0}".format(COSMO_CELERY_URL))

    # install the cosmo celery app to the user home
    runner.sudo("pip install --no-deps -t {0} {1}".format(home, COSMO_CELERY_URL))

    # write cosmo properties
    logger.debug("writing cosmo properties file [node_id=%s]: %s", node_id, cosmo_properties)
    cosmo_properties_path = path.join(app_dir, "cosmo.txt")
    runner.put(StringIO(json.dumps(cosmo_properties)), cosmo_properties_path, use_sudo=True)

    # install the plugin installer dependencies
    runner.sudo("pip install {0}".format(PLUGIN_INSTALLER_URL))

    # install the plugin installer into the worker
    runner.sudo("pip install --no-deps -t {0} {1}".format(create_namespace_path(runner, COSMO_PLUGIN_NAMESPACE,
                                                                                app_dir),
                                                          PLUGIN_INSTALLER_URL))

    # daemonize
    runner.sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    runner.sudo("chmod +x /etc/init.d/celeryd")
    config_file = StringIO(build_celeryd_config(user, home, app, node_id, broker_url))
    runner.put(config_file, "/etc/default/celeryd", use_sudo=True)

    logger.info("starting celery worker")
    runner.sudo("service celeryd start")

    # just to print out the registered tasks for debugging purposes
    runner.sudo("celery inspect registered --broker=" + broker_url)


def create_namespace_path(runner, namespace_parts, base_dir):
    """
    Creates the namespaces path the plugin directory will reside in.
    For example
        input : cloudify.tosca.artifacts.plugin.python_webserver_installer
        output : a directory path app/cloudify/tosca/artifacts/plugin
    "app/cloudify/plugins/host_provisioner". In addition, "__init.py__" files will be created in each of the
    path's sub directories.

    """

    runner.sudo("mkdir -p " + base_dir)
    remote_plugin_path = base_dir
    for folder in namespace_parts:
        remote_plugin_path = os.path.join(remote_plugin_path, folder)
        runner.sudo("mkdir -p " + remote_plugin_path)
        runner.sudo('echo "" > ' + remote_plugin_path + '/__init__.py')

    return remote_plugin_path


def get_machine_ip(cloudify_runtime):
    if not cloudify_runtime:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')

    for value in cloudify_runtime.values():
        if 'ip' in value:
            return value['ip']

    raise ValueError('cannot get machine ip - cloudify_runtime format error')


def build_celeryd_config(user, workdir, app, node_id, broker_url):
    return '''
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
--hostname=%(node_id)s"''' % dict(user=user,
                                  workdir=workdir,
                                  app=app,
                                  node_id=node_id,
                                  broker_url=broker_url)


class FabricRetryingRunner:

    def __init__(self, local=False, host_string=None, key_filename=None):

        """
        If ``local`` is true. the ``host_string`` and ``key_filename`` parameters are ignored
        and all commands will run on the local machine.

        If ``local`` is false. the ``host_string`` and ``key_filename`` are mandatory
        """

        self.local = local
        self.host_string = host_string
        self.key_filename = key_filename

    def run_with_timeout_and_retry(self, fun, *args, **kwargs):
        sleep_interval = 3
        max_retries = 3

        current_retries = 0

        while True:
            try:
                try:
                    if self.local:
                        fun(*args, **kwargs)
                    else:
                        with settings(host_string=self.host_string,
                                      key_filename=self.key_filename,
                                      disable_known_hosts=True):
                            fun(*args, **kwargs)
                    break
                except SystemExit, e:  # fabric just loves them SystemExit folks
                    trace = sys.exc_info()[2]
                    raise RuntimeError('Failed command: {0}'.format(e)), None, trace
            except BaseException:
                if current_retries < max_retries:
                    current_retries += 1
                    time.sleep(sleep_interval)
                else:
                    exception = sys.exc_info()[1]
                    trace = sys.exc_info()[2]
                    raise exception, None, trace

    def sudo(self, command):

        function = sudo
        if self.local:
            function = self._lsudo

        self.run_with_timeout_and_retry(function, command)

    def run(self, command):

        function = run
        if self.local:
            function = lrun

        self.run_with_timeout_and_retry(function, command)

    def put(self, string, remote_file_path, use_sudo=False):

        if self.local:
            self.run_with_timeout_and_retry(self._lput, string, remote_file_path)
            return

        string = StringIO(string)
        self.run_with_timeout_and_retry(put, string, remote_file_path, use_sudo=use_sudo)

    def get(self, file_path):

        """
        Read the file to a string
        """

        if self.local:
            with open(file_path, "r") as f:
                return f.read()

        output = StringIO()
        self.run_with_timeout_and_retry(get, file_path, output)
        return output.getvalue()

    def _lsudo(self, command):

        """
        Run sudo command locally
        """

        lrun("sudo {0}".format(command))

    def _lput(self, string, file_path):

        """
        Write the string to the file specified in file_path
        """

        with open(file_path, "w") as f:
            f.write(string)


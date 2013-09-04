import os
from os.path import expanduser

__author__ = 'elip'

from StringIO import StringIO
from os import path
import time
import sys
import json

from celery.utils.log import get_task_logger
from celery import task
from fabric.api import settings, sudo, run, put, get, hide


COSMO_CELERY_URL = ""
PLUGIN_INSTALLER_URL = ""
COSMO_PLUGIN_NAMESPACE = ["cloudify", "tosca", "artifacts", "plugin"]
logger = get_task_logger(__name__)

_plugins_to_install = ["plugin_installer"]


@task
def install(worker_config, __cloudify_id, cloudify_runtime, **kwargs):
    try:
        prepare_configuration(worker_config, cloudify_runtime)
        install_latest_pip(worker_config, __cloudify_id)
        install_celery_worker(worker_config, __cloudify_id)
    # fabric raises SystemExit on failure, so we transform this to a regular exception.
    except SystemExit, e:
        trace = sys.exc_info()[2]
        raise RuntimeError('Failed celery worker installation: {0}'.format(e)), None, trace


@task
def restart(worker_config, __cloudify_id, cloudify_runtime, **kwargs):
    try:
        prepare_configuration(worker_config, cloudify_runtime)
        restart_celery_worker(worker_config, __cloudify_id)
    # fabric raises SystemExit on failure, so we transform this to a regular exception.
    except SystemExit, e:
        trace = sys.exc_info()[2]
        raise RuntimeError('Failed celery worker restart: {0}'.format(e)), None, trace


def install_latest_pip(worker_config, node_id):
    logger.info("installing latest pip installation [node_id=%s]", node_id)
    print 'worker_config=', worker_config
    print 'node_id=', node_id
    host_string = '%(user)s@%(host)s:%(port)s' % worker_config
    key_filename = worker_config['key']
    with settings(host_string=host_string,
                  key_filename=key_filename,
                  disable_known_hosts=True):
        runner = FabricRetryingRunner()
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


def install_celery_worker(worker_config, node_id):
    print 'worker_config=', worker_config
    print 'node_id=', node_id
    host_string = '%(user)s@%(host)s:%(port)s' % worker_config
    key_filename = worker_config['key']
    with settings(host_string=host_string,
                  key_filename=key_filename,
                  disable_known_hosts=True):
        _install_celery(worker_config, node_id)
        _verify_no_celery_error(worker_config)


def restart_celery_worker(worker_config, node_id):
    print 'worker_config=', worker_config
    print 'node_id=', node_id
    host_string = '%(user)s@%(host)s:%(port)s' % worker_config
    key_filename = worker_config['key']
    with settings(host_string=host_string,
                  key_filename=key_filename,
                  disable_known_hosts=True):
        sudo('service celeryd restart')
        _verify_no_celery_error(worker_config)


def _verify_no_celery_error(worker_config):
    user = worker_config['user']
    home = "/home/" + user
    celery_error_out = '{0}/celery_error.out'.format(home)
    output = StringIO()
    with hide('aborts', 'running', 'stdout', 'stderr'):
        try:
            get(celery_error_out, output)
        except:
            pass

    # this means the celery worker had an uncaught exception and it wrote its content
    # to the file above because of our custom exception handler (see celery.py)
    if output.getvalue():
        FabricRetryingRunner().run('rm {0}'.format(celery_error_out))
        error_content = output.getvalue()
        raise RuntimeError('Celery worker failed to start:\n{0}'.format(error_content))


def _install_celery(worker_config, node_id):

    runner = FabricRetryingRunner()

    logger.info("installing celery worker[node_id=%s]", node_id)

    logger.debug("installing python-pip [node_id=%s]", node_id)
    runner.sudo("apt-get install -q -y python-pip")

    logger.debug("installing billiard using pip [node_id=%s]", node_id)
    runner.sudo("pip install billiard==2.7.3.28")

    logger.debug("installing celery using pip [node_id=%s]", node_id)
    runner.sudo("pip install --timeout=120 celery==3.0.19")

    logger.debug("installing bernhard using pip [node_id=%s]", node_id)
    runner.sudo("pip install --timeout=120 bernhard==0.1.0")

    cosmo_properties = {
        'management_ip': worker_config['management_ip'],
        'ip': worker_config['host']
    }
    user = worker_config['user']
    broker_url = worker_config['broker']
    app = worker_config['app']
    home = "/home/" + user
    app_dir = home + "/" + app

    runner.run("rm -rf " + app_dir)

    # install the cosmo celery app to the user home
    runner.sudo("pip install -t {0} {1}".format(home, COSMO_CELERY_URL))

    # write cosmo properties
    logger.debug("writing cosmo properties file [node_id=%s]: %s", node_id, cosmo_properties)
    cosmo_properties_path = path.join(app_dir, "cosmo.txt")
    runner.put(StringIO(json.dumps(cosmo_properties)), cosmo_properties_path)

    # install the plugin installer dependencies
    runner.sudo("pip install {0}".format(PLUGIN_INSTALLER_URL))

    # install the plugin installer into the worker
    runner.sudo("pip install -t {0} {1}".format(create_namespace_path(COSMO_PLUGIN_NAMESPACE), PLUGIN_INSTALLER_URL))

    #daemonize
    runner.sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    runner.sudo("chmod +x /etc/init.d/celeryd")
    config_file = StringIO(build_celeryd_config(user, home, app, node_id, broker_url))
    runner.put(config_file, "/etc/default/celeryd", use_sudo=True)

    logger.info("starting celery worker")
    runner.sudo("service celeryd start")


def create_namespace_path(namespace_parts):

    """
    Creates the namespaces path the plugin directory will reside in.
    For example
        input : cloudify.tosca.artifacts.plugin.python_webserver_installer
        output : a directory path app/cloudify/tosca/artifacts/plugin
    "app/cloudify/plugins/host_provisioner". In addition, "__init.py__" files will be created in each of the
    path's sub directories.

    """
    home_dir = expanduser("~")
    cosmo_path = os.path.join(home_dir, "cosmo")
    path = cosmo_path

    for p in namespace_parts:
        path = os.path.join(path, p)
    logger.debug("plugin installation path is {0}".format(path))

    if not os.path.exists(path):
        os.makedirs(path)

    # create __init__.py files in each subfolder
    init_path = cosmo_path
    for p in namespace_parts:
        init_path = os.path.join(init_path, p)
        init_file = os.path.join(init_path, "__init__.py")
        if not os.path.exists(init_file):
            open(init_file, "w").close()

    return path


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

    def run_with_timeout_and_retry(self, fun, *args, **kwargs):
        sleep_interval = 3
        max_retries = 3

        current_retries = 0

        while True:
            try:
                try:
                    fun(*args, **kwargs)
                    break
                except SystemExit, e: # fabric just loves them SystemExit folks
                    trace = sys.exc_info()[2]
                    raise RuntimeError('Failed command: {0}'.format(e)), None, trace
            except:
                if current_retries < max_retries:
                    current_retries += 1
                    time.sleep(sleep_interval)
                else:
                    exception = sys.exc_info()[1]
                    trace = sys.exc_info()[2]
                    raise exception, None, trace

    def sudo(self, command):
        self.run_with_timeout_and_retry(sudo, command)

    def run(self, command):
        self.run_with_timeout_and_retry(run, command)        

    def put(self, local, remote, use_sudo=False):
        self.run_with_timeout_and_retry(put, local, remote, use_sudo=use_sudo)

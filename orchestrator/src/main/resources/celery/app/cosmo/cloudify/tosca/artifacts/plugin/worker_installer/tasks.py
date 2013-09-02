__author__ = 'elip'

from StringIO import StringIO
from os import path
import time
import sys
import json

from celery.utils.log import get_task_logger
from fabric.api import settings, sudo, run, put, get, hide

from cosmo.celery import celery as celery


logger = get_task_logger(__name__)

_plugins_to_install = ["plugin_installer"]


@celery.task
def install(worker_config, __cloudify_id, cloudify_runtime, **kwargs):
    try:
        prepare_configuration(worker_config, cloudify_runtime)
        install_latest_pip(worker_config, __cloudify_id)
        install_celery_worker(worker_config, __cloudify_id)
    # fabric raises SystemExit on failure, so we transform this to a regular exception.
    except SystemExit, e:
        trace = sys.exc_info()[2]
        raise RuntimeError('Failed celery worker installation: {0}'.format(e)), None, trace


@celery.task
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

    # create app directory and copy necessary files to it
    runner.run("mkdir " + app_dir)
    script_path = path.realpath(__file__)
    script_dir = path.dirname(script_path)
    runner.put(script_dir + "/remote/__init__.py", app_dir)
    runner.put(script_dir + "/remote/celery.py", app_dir)
    runner.put(script_dir + "/remote/events.py", app_dir)

    # write cosmo properties
    logger.debug("writing cosmo properties file [node_id=%s]: %s", node_id, cosmo_properties)
    cosmo_properties_path = path.join(app_dir, "cosmo.txt")
    runner.put(StringIO(json.dumps(cosmo_properties)), cosmo_properties_path)

    # create app/cloudify/tosca/artifacts/plugin with __init__.py file in each directory
    remote_plugin_path = app_dir
    for dir in ["cloudify", "tosca", "artifacts", "plugin"]:
        remote_plugin_path = path.join(remote_plugin_path, dir)
        runner.run("mkdir " + remote_plugin_path)
        runner.run('echo "" > ' + remote_plugin_path + '/__init__.py')

    logger.info("installing cosmo built in plugins [node_id=%s]", node_id)

    # install plugins (from ../*) according to _plugins_to_install
    plugins_dir = path.abspath(path.join(script_dir, "../"))
    for plugin in _plugins_to_install:
        plugin_dir = path.join(plugins_dir, plugin)
        if not path.exists(plugin_dir):
            raise RuntimeError("plugin [{0}] does not exist [path={1}]".format(plugin, plugin_dir))
        runner.put(plugin_dir, remote_plugin_path)

    #daemonize
    runner.sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    runner.sudo("chmod +x /etc/init.d/celeryd")
    config_file = StringIO(build_celeryd_config(user, home, app, node_id, broker_url))
    runner.put(config_file, "/etc/default/celeryd", use_sudo=True)

    logger.info("starting celery worker")
    runner.sudo("service celeryd start")


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

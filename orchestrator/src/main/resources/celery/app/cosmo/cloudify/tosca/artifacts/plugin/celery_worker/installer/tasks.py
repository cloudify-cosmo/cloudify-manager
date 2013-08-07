__author__ = 'elip'

from StringIO import StringIO

from cosmo.celery import celery as celery
from celery.utils.log import get_task_logger
from fabric.api import settings, sudo, run, put
import socket
import os
from os import path

logger = get_task_logger(__name__)

_plugins_to_install = ["plugin_installer"]


@celery.task
def install(worker_config, __cloudify_id, cloudify_runtime, **kwargs):
    prepare_configuration(worker_config, cloudify_runtime)
    install_celery_worker(worker_config, __cloudify_id)


@celery.task
def restart(worker_config, __cloudify_id, cloudify_runtime, **kwargs):
    prepare_configuration(worker_config, cloudify_runtime)
    restart_celery_worker(worker_config, __cloudify_id)


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


def restart_celery_worker(worker_config, node_id):
    print 'worker_config=', worker_config
    print 'node_id=', node_id
    host_string = '%(user)s@%(host)s:%(port)s' % worker_config
    key_filename = worker_config['key']
    with settings(host_string=host_string,
                  key_filename=key_filename,
                  disable_known_hosts=True):
        sudo('service celeryd restart')


def _install_celery(worker_config, node_id):
    sudo("apt-get install -q -y python-pip")
    sudo("pip install billiard==2.7.3.28")
    sudo("pip install --timeout=120 celery==3.0.19")

    user = worker_config['user']
    management_ip = worker_config['management_ip']
    broker_url = worker_config['broker']
    app = worker_config['app']
    home = "/home/" + user
    app_dir = home + "/" + app

    run("rm -rf " + app_dir)

    # create app directory and copy necessary files to it
    run("mkdir " + app_dir)
    script_path = path.realpath(__file__)
    script_dir = path.dirname(script_path)
    put(script_dir + "/remote/__init__.py", app_dir)
    put(script_dir + "/remote/celery.py", app_dir)

    # create app/cloudify/tosca/artifacts/plugin with __init__.py file in each directory
    remote_plugin_path = app_dir
    for dir in ["cloudify", "tosca", "artifacts", "plugin"]:
        remote_plugin_path = path.join(remote_plugin_path, dir)
        run("mkdir " + remote_plugin_path)
        run('echo "" > ' + remote_plugin_path + '/__init__.py')

    # install plugins (from ../*) according to _plugins_to_install
    plugins_dir = path.abspath(path.join(script_dir, "../.."))
    for plugin in _plugins_to_install:
        plugin_dir = path.join(plugins_dir, plugin)
        if not path.exists(plugin_dir):
            raise RuntimeError("plugin [{0}] does not exist [path={1}]".format(plugin, plugin_dir))
        put(plugin_dir, remote_plugin_path)

    #daemonize
    sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    sudo("chmod +x /etc/init.d/celeryd")
    config_file = StringIO(build_celeryd_config(user, home, app, node_id, broker_url))
    put(config_file, "/etc/default/celeryd", use_sudo=True)
    sudo("service celeryd start")


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
--loglevel=info \
--app=%(app)s \
-Q %(node_id)s \
--broker=%(broker_url)s \
--hostname=%(node_id)s"''' % dict(user=user,
                                   workdir=workdir,
                                   app=app,
                                   node_id=node_id,
                                   broker_url=broker_url)


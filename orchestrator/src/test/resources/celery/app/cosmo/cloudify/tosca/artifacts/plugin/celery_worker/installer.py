__author__ = 'elip'

from StringIO import StringIO

from cosmo.celery import celery as celery
from celery.utils.log import get_task_logger
from fabric.api import settings, sudo, run, put
import socket
from time import sleep

logger = get_task_logger(__name__)

@celery.task
def install(ssh_config, celery_config, __cloudify_id, cloudify_runtime, **kwargs):
    ip = get_machine_ip(cloudify_runtime)
    ssh_config['host'] = ip
    install_celery_worker(ssh_config, celery_config, __cloudify_id)

def install_celery_worker(ssh_conf, celery_conf, node_id):
    print 'celery_config=', celery_conf
    print 'ssh_config=', ssh_conf
    print 'node_id=', node_id
    host_string = '%(user)s@%(host)s:%(port)s' % ssh_conf
    key_filename = ssh_conf['key']
    with settings(host_string=host_string,
        key_filename=key_filename,
        disable_known_hosts=True):
        _install_celery(celery_conf, node_id)

def _install_celery(celery_conf, node_id):

    sudo("apt-get install -q -y python-pip")
    sudo("pip install billiard==2.7.3.28")
    sudo("pip install celery==3.0.19")

    user = celery_conf['user']
    broker_url = celery_conf['broker']
    app = celery_conf['app']
    home = "/home/" + user
    # copy app folder to remote home directory
    run("rm -rf " + home + "/" + app)
    put(celery_conf['local-app-dir'], home)

    #daemonize
    sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    sudo("chmod +x /etc/init.d/celeryd")
    config_file = StringIO(build_celeryd_config(user, home, app, node_id,
        ['cosmo.cloudify.tosca.artifacts.plugin.plugin_installer.installer'], broker_url))
    put(config_file, "/etc/default/celeryd", use_sudo=True)
    sudo("service celeryd start")


def get_machine_ip(cloudify_runtime):
    if not cloudify_runtime:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')

    for value in cloudify_runtime.values():
        if 'ip' in value:
            return value['ip']

    raise ValueError('cannot get machine ip - cloudify_runtime format error')


def build_celeryd_config(user, workdir, app, node_id, include, broker_url):
    return '''
CELERYD_USER="%(user)s"
CELERYD_GROUP="%(user)s"
CELERY_TASK_SERIALIZER="json"
CELERY_RESULT_SERIALIZER="json"
CELERY_RESULT_BACKEND="amqp"
CELERYD_CHDIR="%(workdir)s"
CELERYD_OPTS="\
--events\
--loglevel=info \
--app=%(app)s \
-Q %(node_id)s \
--include=%(include)s \
--broker=%(broker_url)s''' % dict(user=user,
                                  workdir=workdir,
                                  app=app,
                                  node_id=node_id,
                                  include=','.join(include),
                                  broker_url=broker_url)

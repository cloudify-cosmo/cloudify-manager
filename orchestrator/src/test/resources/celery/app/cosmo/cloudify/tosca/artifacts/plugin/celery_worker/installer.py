__author__ = 'elip'

from StringIO import StringIO

from cosmo.celery import celery as celery
from celery.utils.log import get_task_logger
from fabric.api import settings, sudo, run, put
import socket


logger = get_task_logger(__name__)

@celery.task
def install(__cloudify_id, cloudify_runtime, **kwargs):
    ip = get_machine_ip(cloudify_runtime)
    ssh_config = {
        'host': ip,
        'user': 'vagrant',
        'port': 22,
        'key': 'C:\Users\elip\.vagrant.d\insecure_private_key'
    }
    celery_config = {
        'user': 'vagrant',
        'app': 'cosmo',
        'local-app-dir': 'C:\Users\elip\dev\cosmo\cosmo-manager\orchestrator\src\\test\\resources\celeryremote\\app'
                         '\\cosmo',
        'broker': 'amqp://guest:guest@192.168.10.104:5672//',
    }
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

    user = celery_conf['user']
    broker_url = celery_conf['broker']
    app = celery_conf['app']

    home = "/home/" + user
    put(celery_conf['local-app-dir'], home)

    sudo("apt-get install -q -y python-pip")
    sudo("pip install billiard==2.7.3.28")
    sudo("pip install celery==3.0.19")
    run("cd " + home + "; nohup celery worker --events --app=" + app +
        " --include=cosmo.cloudify.tosca.artifacts.plugin.plugin_installer.installer" + " --broker=" + broker_url +
        " -Q " + node_id + " &; cat nohup.out")

"""
    #daemonize
    sudo("wget https://raw.github.com/celery/celery/3.0/extra/generic-init.d/celeryd -O /etc/init.d/celeryd")
    sudo("chmod +x /etc/init.d/celeryd")
    user = celery_conf['user']
    broker_url = celery_conf['broker']
    home = "/home/" + user
    app = celery_conf['app']
    config_file = StringIO('''
CELERYD_USER="''' + user + '''"
CELERY_TASK_SERIALIZER="json"
CELERY_RESULT_SERIALIZER="json"
BROKER_URL="''' + broker_url + '''"
CELERY_RESULT_BACKEND="amqp"
CELERYD_CHDIR="''' + home + '''"
CELERYD_OPTS="--events --loglevel=info --app=''' + app + ''' -Q ''' + node_id + ''' --include=cloudify.tosca.artifacts.plugin.plugin_installer.installer"
    ''')
    put(config_file, "/etc/default/celeryd", use_sudo=True)
    # copy app folder to remote home directory
    run("rm -rf " + home + "/" + app)
    put(celery_conf['local-app-dir'], home)
    sudo("service celeryd start")
    """

def get_machine_ip(cloudify_runtime):
    if cloudify_runtime is None:
        raise ValueError('cannot get machine ip - cloudify_runtime is not set')
    try:
        for key in cloudify_runtime:
            return cloudify_runtime[key]['ip']
    except:
        pass
    raise ValueError('cannot get machine ip - cloudify_runtime format error')

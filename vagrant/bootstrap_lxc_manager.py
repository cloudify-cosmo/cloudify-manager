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

import argparse
import getpass
import subprocess
import re
import threading
import os
import datetime
import time
import sys
import tempfile
import yaml
import es_schema_creator
from os.path import expanduser
from subprocess import check_output


__author__ = 'elip'

FNULL = open(os.devnull, 'w')

USER_HOME = expanduser('~')

FILE_SERVER_PORT = 53229
FILE_SERVER_BLUEPRINTS_FOLDER = 'blueprints'

FABRIC_RUNNER_VERSION = 'develop'
FABRIC_RUNNER = "https://github.com/CloudifySource/" \
                "cosmo-fabric-runner/archive/{0}.zip"\
                .format(FABRIC_RUNNER_VERSION)

WORKER_INSTALLER_VERSION = 'develop'

WORKER_INSTALLER = "https://github.com/CloudifySource/" \
                   "cosmo-plugin-agent-installer/archive/{0}.zip" \
    .format(WORKER_INSTALLER_VERSION)


class RiemannProcess(object):
    """
    Manages a riemann server process lifecycle.
    """
    pid = None
    _config_path = None
    _process = None
    _detector = None
    _event = None
    _riemann_logs = list()

    def __init__(self, config_path):
        self._config_path = config_path

    def _start_detector(self, process):
        pid_pattern = ".*PID\s(\d*)"
        started_pattern = ".*Hyperspace core online"
        while True:
            line = process.stdout.readline().rstrip()
            self._riemann_logs.append(line)
            if line != '':
                if not self.pid:
                    match = re.match(pid_pattern, line)
                    if match:
                        self.pid = int(match.group(1))
                else:
                    match = re.match(started_pattern, line)
                    if match:
                        self._event.set()
                        break

    def start(self):
        print "Starting riemann server..."
        self.pid = self.find_existing_riemann_process()
        if self.pid:
            print "Riemann server already running [pid={0}]".format(self.pid)
            return
        command = [
            'riemann',
            self._config_path
        ]
        self._process = subprocess.Popen(command,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        self._event = threading.Event()
        self._detector = threading.Thread(target=self._start_detector,
                                          kwargs={'process': self._process})
        self._detector.start()
        if not self._event.wait(60):
            raise RuntimeError("Unable to start riemann process:\n{0}"
                               .format('\n'.join(self._riemann_logs)))
        print "Riemann server started [pid={0}]".format(self.pid)

    def close(self):
        if self.pid:
            print "Shutting down riemann server [pid={0}]".format(self.pid)
            os.system("kill {0}".format(self.pid))

    def find_existing_riemann_process(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output(
                "ps aux | grep 'riemann.jar' | grep -v grep", shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None


class WorkflowServiceProcess(object):

    def __init__(self, workflow_service_path, port=8101):
        self.process_grep = 'unicorn master'
        self.port = port
        self.workflow_service_path = workflow_service_path

    def start(self, start_timeout=120):
        output_file = open('workflow-service.out', 'w')
        endtime = time.time() + start_timeout
        command = ["bash --login -i -c 'unicorn -l 0.0.0.0:{0}'"
                   .format(str(self.port))]
        env = os.environ.copy()
        env['RACK_ENV'] = 'development'

        print "starting workflow service with command: {0}".format(command)

        self._process = subprocess.Popen(command,
                                         stdin=FNULL,
                                         stdout=output_file,
                                         stderr=output_file,
                                         env=env,
                                         shell=True,
                                         cwd=self.workflow_service_path)
        self.wait_for_service_started(endtime)
        self.wait_for_service_responsiveness(endtime)

    def find_existing_pid(self):
        from subprocess import CalledProcessError
        pattern = "\w*\s*(\d*).*"
        try:
            output = subprocess.check_output(
                "ps aux | grep '{0}' | grep -v grep"
                .format(self.process_grep), shell=True)
            match = re.match(pattern, output)
            if match:
                return int(match.group(1))
        except CalledProcessError:
            pass
        return None

    def wait_for_service_started(self, endtime):
        while time.time() < endtime:
            self._pid = self.find_existing_pid()
            if self._pid is not None:
                break
            time.sleep(1)

    def wait_for_service_responsiveness(self, endtime):
        import urllib2
        service_url = "http://localhost:{0}".format(self.port)
        up = False
        res = None
        while time.time() < endtime:
            try:
                res = urllib2.urlopen(service_url)
                up = res.code == 200
                break
            except BaseException:
                pass
            time.sleep(1)
        if not up:
            raise RuntimeError("Ruote service is not responding @ {0} "
                               "(response: {1})".format(service_url, res))


class ManagerRestProcess(object):

    def __init__(self,
                 manager_rest_path,
                 file_server_dir,
                 file_server_base_uri,
                 workflow_service_base_uri,
                 file_server_blueprints_folder,
                 port=8100):
        self.file_server_dir = file_server_dir
        self.file_server_base_uri = file_server_base_uri
        self.port = port
        self.manager_rest_path = manager_rest_path
        self.workflow_service_base_uri = workflow_service_base_uri
        self.file_server_blueprints_folder = file_server_blueprints_folder

    def start(self, start_timeout=60):
        output_file = open('manager-rest.out', 'w')
        endtime = time.time() + start_timeout

        configuration = {
            'file_server_root': self.file_server_dir,
            'file_server_base_uri': self.file_server_base_uri,
            'workflow_service_base_uri': self.workflow_service_base_uri,
            'file_server_blueprints_folder': self.file_server_blueprints_folder
        }

        config_path = tempfile.mktemp()
        with open(config_path, 'w') as f:
            f.write(yaml.dump(configuration))
        env = os.environ.copy()
        env['MANAGER_REST_CONFIG_PATH'] = config_path

        command = [
            'gunicorn',
            '-w', '1',
            '-b', '0.0.0.0:{0}'.format(self.port),
            '--timeout', '300',
            'server:app'
        ]

        print "starting manager rest service with command: {0}".format(command)

        self._process = subprocess.Popen(command,
                                         env=env,
                                         stdin=FNULL,
                                         stdout=output_file,
                                         stderr=output_file,
                                         cwd='{0}/manager_rest'.format(
                                             self.manager_rest_path))
        self.wait_for_service_responsiveness(endtime)

    def wait_for_service_responsiveness(self, endtime):
        import urllib2
        service_url = 'http://localhost:{0}/blueprints'.format(self.port)
        up = False
        res = None
        while time.time() < endtime:
            try:
                res = urllib2.urlopen(service_url)
                up = res.code == 200
                break
            except BaseException:
                pass
            time.sleep(1)
        if not up:
            raise RuntimeError("Manager rest service is not responding @ {0} "
                               "(response: {1})".format(service_url, res))


class VagrantLxcBoot:

    RIEMANN_PID = "RIEMANN_PID"
    RIEMANN_CONFIG = "RIEMANN_CONFIG"
    MANAGEMENT_IP = "MANAGEMENT_IP"
    MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL = \
        "MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL"
    BROKER_URL = "BROKER_URL"
    MANAGER_REST_PORT = "MANAGER_REST_PORT"

    def __init__(self, args):
        self.working_dir = args.working_dir
        self.config_dir = args.config_dir
        self.cosmo_version = args.cosmo_version
        self.update_only = args.update_only
        self.install_openstack_provisioner = args.install_openstack_provisioner
        self.management_ip = args.management_ip
        self.install_vagrant_lxc = args.install_vagrant_lxc
        self.install_logstash = args.install_logstash

    def run_command(self, command):
        p = subprocess.Popen(command.split(" "),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            raise RuntimeError("Failed running command {0} [returncode={1}, "
                               "output={2}, error={3}]".format(command,
                                                               out, err,
                                                               p.returncode))
        return out

    def install_fabric_runner(self):
        self.run_command("sudo pip install {0}".format(FABRIC_RUNNER))
        from cosmo_fabric.runner import FabricRetryingRunner
        self.runner = FabricRetryingRunner(local=True)

    def pip(self, package):
        self.runner.sudo("pip install --timeout=120 {0}".format(package))

    def apt_get(self, command):
        self.runner.sudo("apt-get {0}".format(command))

    def add_apt(self, command):
        self.runner.sudo("add-apt-repository {0}".format(command))

    def apt_key(self, command):
        self.runner.sudo("apt-key add {0}".format(command))

    def wget(self, url, output_name=None):
        if output_name is None:
            self.runner.run("wget -q -N {0} -P {1}/"
                            .format(url, self.working_dir))
        else:
            self.runner.run("wget -q -N {0} -P {1}/ -O {2}"
                            .format(url, self.working_dir, output_name))

    # TODO: quiet
    def extract_tar_gz(self, path):
        self.runner.run('tar xzvf {0}'.format(path))

    def install_rabbitmq(self):
        self.runner.sudo("sed -i '2i deb http://www.rabbitmq.com/debian/ "
                         "testing main' /etc/apt/sources.list")
        self.wget("http://www.rabbitmq.com/rabbitmq-signing-key-public.asc")
        self.apt_key("rabbitmq-signing-key-public.asc")
        self.apt_get("update")
        self.apt_get("install -q -y erlang-nox")
        self.apt_get("install -y -f ")
        self.apt_get("install -q -y rabbitmq-server")
        self.runner.sudo("rabbitmq-plugins enable rabbitmq_management")
        self.runner.sudo("rabbitmq-plugins enable rabbitmq_tracing")
        self.runner.sudo("service rabbitmq-server restart")
        self.runner.sudo("rabbitmqctl trace_on")

    def install_lxc_docker(self):
        self.apt_get("install -q -y python-software-properties")
        self.apt_get("update -qq")
        self.add_apt("-y ppa:dotcloud/lxc-docker")
        self.apt_get("update -qq")
        self.apt_get("install -q -y lxc-docker")

    def install_kernel(self):
        self.add_apt("-y ppa:ubuntu-x-swat/r-lts-backport")
        self.apt_get("update -qq")
        self.apt_get("install -q -y linux-image-3.8.0-19-generic")

    def install_riemann(self):
        self.wget("http://aphyr.com/riemann/riemann_0.2.2_all.deb")
        self.runner.sudo("dpkg -i riemann_0.2.2_all.deb")
        riemann_work_path, riemann_config_path = self._get_riemann_paths()
        if os.path.exists(riemann_work_path):
            self.runner.run("rm -rf {0}".format(riemann_work_path))
        os.makedirs(riemann_work_path)
        self.runner.run("cp {0} {1}".format("{0}/riemann.config"
                                            .format(self.config_dir),
                        riemann_config_path))
        riemann = RiemannProcess(riemann_config_path)
        riemann.start()

    def _get_riemann_paths(self):
        riemann_work_path = os.path.join(self.working_dir, 'riemann')
        riemann_config_path = os.path.join(riemann_work_path, 'riemann.config')
        return riemann_work_path, riemann_config_path

    def install_java(self):
        self.apt_get("install -y openjdk-7-jdk")

    def install_ruby(self):
        self.apt_get('install -q -y build-essential git-core curl '
                     'libmysqlclient18')
        self.wget('https://get.rvm.io', 'install_rvm.sh')
        self.runner.run('bash install_rvm.sh stable')
        self.runner.run('bash --login -i -c "rvm install ruby-2.1.0"')
        self.runner.run('bash --login -i -c "rvm --default use ruby-2.1.0"')
        self.runner.run('bash --login -i -c "gem install bundler"')

    def install_cosmo_manager(self):
        cosmo_manager_repo = 'CloudifySource/cosmo-manager'
        branch = self.cosmo_version

        workflow_service_base_uri = 'http://localhost:8101'

        tar_output_name = 'cosmo-manager.tar.gz'
        cosmodir = 'cosmo-manager-{0}'.format(branch.replace('/', '-'))
        self.install_ruby()
        self.wget('https://github.com/{0}/archive/{1}.tar.gz'
                  .format(cosmo_manager_repo, branch), tar_output_name)
        self.extract_tar_gz(tar_output_name)
        manager_rest_path = os.path.abspath(
            '{0}/manager-rest'.format(cosmodir))
        self.pip('{0}/'.format(manager_rest_path))
        prev_cwd = os.getcwd()
        workflow_service_path = os.path.abspath('{0}/workflow-service'
                                                .format(cosmodir))
        os.chdir(workflow_service_path)
        try:
            self.runner.run('bash --login -i -c '
                            '"bundle install --without test"')
        finally:
            os.chdir(prev_cwd)
        workflow_service = WorkflowServiceProcess(workflow_service_path)
        workflow_service.start()

        file_server_dir = tempfile.mkdtemp()
        file_server_base_uri = 'http://localhost:{0}'.format(FILE_SERVER_PORT)

        self.start_file_server(file_server_dir)

        manager_rest = ManagerRestProcess(manager_rest_path,
                                          file_server_dir,
                                          file_server_base_uri,
                                          workflow_service_base_uri,
                                          FILE_SERVER_BLUEPRINTS_FOLDER)
        manager_rest.start()

    def start_file_server(self, file_server_dir, timeout=10):
        endtime = time.time() + timeout

        from manager_rest.file_server import FileServer
        from manager_rest.util import copy_resources

        file_server_process = FileServer(file_server_dir, use_subprocess=True)
        file_server_process.start()
        while not file_server_process.is_alive() and time.time() < endtime:
            time.sleep(1)
        if not file_server_process.is_alive():
            raise RuntimeError("File server is not responding")

        orchestrator_dir = os.path.abspath(__file__)
        for i in range(2):
            orchestrator_dir = os.path.dirname(orchestrator_dir)
        orchestrator_dir = os.path.join(orchestrator_dir,
                                        'orchestrator')
        copy_resources(file_server_dir, orchestrator_dir)

    def install_celery_worker(self):

        # download and install the worker_installer
        self.pip(WORKER_INSTALLER)

        worker_config = {
            "user": getpass.getuser(),
            "broker": "amqp://",
            "management": True,
            "env": {
                "VAGRANT_DEFAULT_PROVIDER": "lxc",
                # when running celery in daemon mode. this environment does
                # not exists. it is needed for vagrant.
                "HOME": expanduser("~"),
                self.MANAGEMENT_IP: self.management_ip,
                self.BROKER_URL: "amqp://guest:guest@{0}:5672//"
                                 .format(self.management_ip),
                self.MANAGER_REST_PORT: "8100",
                self.MANAGER_FILE_SERVER_BLUEPRINTS_ROOT_URL:
                "http://{0}:{1}/{2}".format(self.management_ip,
                                            FILE_SERVER_PORT,
                                            FILE_SERVER_BLUEPRINTS_FOLDER),
            }
        }

        from cloudify.constants import MANAGEMENT_NODE_ID

        runtime_properties = {
            'ip': MANAGEMENT_NODE_ID
        }

        from cloudify.mocks import MockCloudifyContext
        ctx = MockCloudifyContext(node_id="cloudify.management",
                                  runtime_properties=runtime_properties)

        # # install the worker locally
        from worker_installer.tasks import install as install_worker
        install_worker(ctx, worker_config=worker_config, local=True)

        # start the worker now for all plugins to be registered
        from worker_installer.tasks import start
        start(ctx, worker_config=worker_config, local=True)

    def install_vagrant(self):
        vagrant_file_name = "vagrant_1.2.7_x86_64.deb"
        vagrant_file_path = os.path.join(self.working_dir, vagrant_file_name)
        if os.path.exists(vagrant_file_path):
            self.runner.run("rm -rf {0}".format(vagrant_file_path))
        self.wget(
            "http://files.vagrantup.com/packages/"
            "7ec0ee1d00a916f80b109a298bab08e391945243/{0}"
            .format(vagrant_file_name)
        )
        self.runner.sudo("dpkg -i vagrant_1.2.7_x86_64.deb")
        self._install_vagrant_lxc()
        self.add_lxc_box("precise64",
                         "http://dl.dropbox.com/u/13510779/"
                         "lxc-precise-amd64-2013-07-12.box")

    def _install_vagrant_lxc(self):
        self.runner.run("vagrant plugin install vagrant-lxc")

    def install_guest_additions(self):
        """
        Currently not used. provides some more functionality between the actual
        host and the virtual box vagrant guest.
        See http://www.virtualbox.org/manual/ch04.html
        """
        self.apt_get("install -q -y linux-headers-3.8.0-19-generic dkms")
        self.runner.run("echo 'Downloading VBox Guest Additions...'")
        self.wget("-q http://dlc.sun.com.edgesuite.net/"
                  "virtualbox/4.2.12/VBoxGuestAdditions_4.2.12.iso")

        guest_additions_script = """mount -o loop,ro \
/home/vagrant/VBoxGuestAdditions_4.2.12.iso /mnt
echo yes | /mnt/VBoxLinuxAdditions.run
umount /mnt
rm /root/guest_additions.sh
"""

        self.runner.run("echo -e '" + guest_additions_script +
                        "' > /root/guest_additions.sh")
        self.runner.run("chmod 700 /root/guest_additions.sh")
        self.runner.run(
            "sed -i -E 's#^exit 0#[ -x /root/guest_additions.sh ] "
            "\\&\\& /root/guest_additions.sh#' /etc/rc.local"
        )
        self.runner.run("echo 'Installation of VBox Guest Additions is "
                        "proceeding in the background.'")
        self.runner.run("echo '\"vagrant reload\" can be used in about 2 "
                        "minutes to activate the new guest additions.'")

    def add_lxc_box(self, name, url):
        pattern = "precise64.*"
        output = subprocess.check_output(["vagrant", "box", "list"])
        match = re.match(pattern, output)
        if match:
            print "precise64 box already installed"
        else:
            self.runner.run(
                "vagrant box add {0} {1}".format(name, url)
            )

    def install_python_protobuf(self):
        self.apt_get("install -y python-protobuf")

    def reboot(self):
        self.runner.sudo("shutdown -r +1")

    def get_machine_ip_addresses(self):
        output = check_output(["ip", "a"])
        output = output.replace('\n', '')
        ips_pattern = "<(.+?)>.*?inet\s(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        ips = re.findall(ips_pattern, output)
        return map(lambda ip_info: ip_info[1],
                   filter(lambda x: "loopback" not in x[0].lower(), ips))

    def set_management_ip(self):
        try:
            ips = self.get_machine_ip_addresses()
            if self.management_ip:
                if self.management_ip not in ips:
                    print('Could not set management ip!\n' +
                          'Specified management ip is not listed in '
                          'machine\'s assigned ip addresses: {0}'.format(ips))
                    sys.exit(1)
            else:
                if len(ips) == 1:
                    self.management_ip = ips[0]
                else:
                    print('Could not set management ip!\n' +
                          'IP addresses assigned to this machine: {0}\n'
                          .format(ips) +
                          'Run this script with \'--managemant_ip\' argument '
                          'for specifying the management ' +
                          'machine ip address which should be one of the ips '
                          'assigned to this machine')
                    sys.exit(1)
            print("Management ip is set to: {0}".format(self.management_ip))
        except SystemExit as e:
            raise e
        except BaseException:
            print('Could not set management ip!\n' +
                  'Run this script with \'--managemant-ip\' argument for '
                  'specifying the management ' +
                  'machine ip address which should be one of the ips '
                  'assigned to this machine')
            sys.exit(1)

    def _install_logstash(self):
        logstash_jar_name = "logstash-1.3.3-flatjar.jar"
        self.wget("https://download.elasticsearch.org/logstash/logstash/{0}"
                  .format(logstash_jar_name))
        logstash_jar_path = os.path.join(self.working_dir, logstash_jar_name)
        logstash_web_port = 8080
        logstash_config_path = os.path.join(self.config_dir, 'logstash.conf')
        if not os.path.exists(logstash_config_path):
            raise RuntimeError("logstash configuration file [{0}] "
                               "does not exist".format(logstash_config_path))
        # Starts logstash with Kibana listening on port 8080
        command = "java -Xmx1024m -Xms256m -jar {0} agent -f {1}" \
                  " -- web --port {2}".format(logstash_jar_path,
                                              logstash_config_path,
                                              logstash_web_port).split(' ')
        timeout_seconds = 60
        print("Starting logstash with web port set to: {0} "
              "[timeout={1} seconds]".format(logstash_web_port,
                                             timeout_seconds))
        self._process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        timeout = datetime.datetime.now() + datetime.timedelta(
            seconds=timeout_seconds)
        timeout_exceeded = False
        pattern = ".*8080.*LISTEN"
        # Wait until logstash web port is in listening state
        while not timeout_exceeded:
            output = check_output(["netstat", "-nl"]).replace('\n', '')
            match = re.match(pattern, output)
            if match:
                break
            timeout_exceeded = datetime.datetime.now() > timeout
            time.sleep(1)
        if timeout_exceeded:
            raise RuntimeError("Failed to start logstash within a timeout "
                               "of {0} seconds".format(timeout_seconds))
        print("Logstash has been successfully started")

    def _run_elasticsearch_schema_creator(self):
        es_schema_creator.create_schema(es_schema_creator.STORAGE_INDEX_URL)

    def bootstrap(self):
        os.chdir(self.working_dir)
        self.set_management_ip()
        self.install_fabric_runner()
        if not self.update_only:
            self.install_python_protobuf()
            self.install_rabbitmq()
            self.install_java()
            if self.install_vagrant_lxc:
                self.install_lxc_docker()
                self.install_kernel()
                self.install_vagrant()
            self.install_riemann()
            if self.install_logstash:
                self._install_logstash()
                self._run_elasticsearch_schema_creator()
            self.install_cosmo_manager()
            self.install_celery_worker()
        else:
            # just update the worker
            try:
                self.runner.sudo("service celeryd stop")
            except BaseException as e:
                print "Failed stopping celeryd service. maybe it was not " \
                      "running? : {0}".format(e.message)
            self.runner.sudo("rm -rf cosmo_celery_common-*")
            self.install_celery_worker()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Boots and installs all necessary cosmo management '
                    'components'
    )
    parser.add_argument(
        '--working_dir',
        help='Working directory for all cosmo installation files',
        default="/home/vagrant/cosmo-work"
    )
    parser.add_argument(
        '--config_dir',
        help='Directory in which files such as log4j.properties and '
             'riemann.config reside',
        default='/vagrant'
    )
    parser.add_argument(
        '--cosmo_version',
        help='Version of cosmo that will be used to deploy the dsl',
        default='develop'
    )
    parser.add_argument(
        '--update_only',
        help='Update the cosmo agent on this machine with new '
             'plugins from github',
        action="store_true",
        default=False
    )
    parser.add_argument(
        '--install_openstack_provisioner',
        help='Whether the openstack host provisioner should be '
             'installed in the management celery worker',
        action="store_true",
        default=False
    )
    parser.add_argument(
        '--management_ip',
        help='Specifies the IP address to be used for the management machine '
             '(should be set to one of the available ' +
             'IP addresses assigned to this machine)',
        default=None
    )

    parser.add_argument(
        '--install_vagrant_lxc',
        help="Specifies whether Vagrant and LXC would be installed for "
             "LXC host provisioning",
        action="store_true",
        default=False
    )

    parser.add_argument(
        '--install_logstash',
        help="Specifies whether to install and run logstash for analyzing "
             "cosmo events",
        action="store_true",
        default=False
    )

    print("Cloudify Cosmo [{0}] Management Machine Bootstrap")

    vagrant_boot = VagrantLxcBoot(parser.parse_args())
    vagrant_boot.bootstrap()

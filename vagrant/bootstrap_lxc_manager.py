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

import argparse
import getpass
from os.path import expanduser
import subprocess

__author__ = 'elip'

FABRIC_RUNNER = "https://github.com/CloudifySource/cosmo-fabric-runner/archive/master.zip"

PLUGIN_INSTALLER = "https://github.com/CloudifySource/cosmo-plugin-plugin-installer/archive/develop.zip"

from management_plugins import WORKER_INSTALLER

USER_HOME = expanduser('~')


class VagrantLxcBoot:

    def __init__(self, args):
        self.working_dir = args.working_dir
        self.cosmo_version = args.cosmo_version
        self.jar_name = "orchestrator-" + self.cosmo_version + "-all"
        self.update_only = args.update_only

    def run_command(self, command):
        p = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            raise RuntimeError("Failed running command {0} [returncode={1}, "
                               "output={2}, error={3}]".format(command, out, err, p.returncode))
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

    def wget(self, url):
        self.runner.run("wget {0} -P {1}/".format(url, self.working_dir))

    def install_rabbitmq(self):
        self.runner.sudo("sed -i '2i deb http://www.rabbitmq.com/debian/ testing main' /etc/apt/sources.list")
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

    def install_java(self):
        self.apt_get("install -y openjdk-7-jdk")

    def install_celery(self):
        self.pip("billiard==2.7.3.28")
        self.pip("celery==3.0.19")
        self.pip("python-vagrant")
        self.pip("bernhard")

    def install_celery_worker(self):

        # download and install the worker_installer
        self.pip(WORKER_INSTALLER)

        # no need to specify port and key file. we are installing locally
        local_ip = "127.0.0.1"

        worker_config = {
            "user": getpass.getuser(),
            "management_ip": local_ip,
            "broker": "amqp://",
            "env": {
                "VAGRANT_DEFAULT_PROVIDER": "lxc",
                # when running celery in daemon mode. this environment does
                # not exists. it is needed for vagrant.
                "HOME": "/home/{0}".format(getpass.getuser())
            }
        }

        cloudify_runtime = {
            "cloudify.management": {
                "ip": local_ip
            }
        }

        __cloudify_id = "cloudify.management"

        # # install the worker locally
        from worker_installer.tasks import install as install_worker
        install_worker(worker_config=worker_config,
                       __cloudify_id=__cloudify_id,
                       cloudify_runtime=cloudify_runtime,
                       local=True)

        # install the necessary management plugins.
        self.install_management_plugins()

        # start the worker now for all plugins to be registered
        from worker_installer.tasks import start
        start(worker_config=worker_config, cloudify_runtime=cloudify_runtime, local=True)

        # uninstall the plugin installer from python installation. not needed anymore.
        self.runner.sudo("pip uninstall -y cosmo-plugin-plugin-installer")

    def install_management_plugins(self):

        # download and install the plugin_installer
        self.pip(PLUGIN_INSTALLER)

        # install the management plugins
        from plugin_installer.tasks import install_celery_plugin_to_dir as install_plugin

        from management_plugins import plugins
        for plugin in plugins:
            install_plugin(plugin=plugin)

    def install_vagrant(self):

        self.wget(
            "http://files.vagrantup.com/packages/7ec0ee1d00a916f80b109a298bab08e391945243/vagrant_1.2.7_x86_64.deb"
        )
        self.runner.sudo("dpkg -i vagrant_1.2.7_x86_64.deb")
        self.install_vagrant_lxc()
        self.add_lxc_box("precise64", "http://dl.dropbox.com/u/13510779/lxc-precise-amd64-2013-07-12.box")

    def install_vagrant_lxc(self):
        self.runner.run("vagrant plugin install vagrant-lxc")

    """
    Currently not used. provides some more functionallity between the actual host and the virtual box vagrant guest.
    See http://www.virtualbox.org/manual/ch04.html
    """
    def install_guest_additions(self):
        self.apt_get("install -q -y linux-headers-3.8.0-19-generic dkms")
        self.runner.run("echo 'Downloading VBox Guest Additions...'")
        self.wget("-q http://dlc.sun.com.edgesuite.net/virtualbox/4.2.12/VBoxGuestAdditions_4.2.12.iso")

        guest_additions_script = """mount -o loop,ro /home/vagrant/VBoxGuestAdditions_4.2.12.iso /mnt
echo yes | /mnt/VBoxLinuxAdditions.run
umount /mnt
rm /root/guest_additions.sh
"""

        self.runner.run("echo -e '" + guest_additions_script + "' > /root/guest_additions.sh")
        self.runner.run("chmod 700 /root/guest_additions.sh")
        self.runner.run(
            "sed -i -E 's#^exit 0#[ -x /root/guest_additions.sh ] \\&\\& /root/guest_additions.sh#' /etc/rc.local"
        )
        self.runner.run("echo 'Installation of VBox Guest Additions is proceeding in the background.'")
        self.runner.run("echo '\"vagrant reload\" can be used in about 2 minutes to activate the new guest additions.'")

    def install_cosmo(self):

        run_script = """#!/bin/sh
if [ $# -gt 0 ] && [ "$1" = "undeploy" ]
then
        echo "Undeploying..."
        curdir=`pwd`
        for dir in /tmp/vagrant-vms/*/
        do
                if [ -d "$dir" ]; then
                        cd $dir
                        vagrant destroy -f > /dev/null 2>&1
                fi
        done
        cd $curdir
        rm -rf /tmp/vagrant-vms/*
        echo "done!"
else
        ARGS="$@"
        java -Xms512m -Xmx1024m -XX:PermSize=128m -Dlog4j.configuration=file://{0}/log4j.properties -jar {0}/cosmo.jar $ARGS
fi
""".format(self.working_dir)

        get_cosmo = "https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/" \
                    ".m2/repository/org/cloudifysource/cosmo/orchestrator/" + self.cosmo_version + "/" + self\
            .jar_name + ".jar"

        self.wget(get_cosmo)

        self.runner.run("mv {0}/{1}.jar cosmo.jar".format(self.working_dir, self.jar_name))
        self.runner.run("cp {0} {1}".format("/vagrant/log4j.properties", self.working_dir))

        script_path = self.working_dir + "/cosmo.sh"
        cosmo_exec = open(script_path, "w")
        cosmo_exec.write(run_script)

        self.runner.run("chmod +x " + script_path)

        self.runner.run("echo \"alias cosmo='{0}/cosmo.sh'\" > {1}/.bash_aliases".format(self.working_dir, USER_HOME))

    def add_lxc_box(self, name, url):
        self.runner.run(
            "vagrant box add {0} {1}".format(name, url)
        )

    def install_python_protobuf(self):
        self.apt_get("install -y python-protobuf")

    def reboot(self):
        self.runner.sudo("shutdown -r +1")

    def bootstrap(self):
        self.install_fabric_runner()
        if not self.update_only:
            self.install_python_protobuf()
            self.install_rabbitmq()
            self.install_lxc_docker()
            self.install_kernel()
            self.install_riemann()
            self.install_vagrant()
            self.install_java()
            self.install_cosmo()
            self.install_celery_worker()
        else:
            # just update the worker
            # self.runner.sudo("service celeryd stop")
            self.runner.sudo("rm -rf /home/vagrant/cosmo")
            self.runner.sudo("rm -rf cosmo_celery_common-0.1.0.egg-info")
            self.install_celery_worker()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Boots and installs all necessary cosmo management components'
    )
    parser.add_argument(
        '--working_dir',
        help='Working directory for all cosmo installation files',
        default="/home/vagrant/cosmo-work"
    )
    parser.add_argument(
        '--cosmo_version',
        help='Version of cosmo that will be used to deploy the dsl',
        default='0.1-SNAPSHOT'
    )
    parser.add_argument(
        '--update_only',
        help='Update the cosmo agent on this machine with new plugins from github',
        default=False,
    )

    vagrant_boot = VagrantLxcBoot(parser.parse_args())
    vagrant_boot.bootstrap()
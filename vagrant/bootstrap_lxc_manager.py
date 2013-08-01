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
from os.path import expanduser
import subprocess
import sys

__author__ = 'elip'

from subprocess import CalledProcessError
from retrying import retry
import timeout_decorator

USER_HOME = expanduser('~')
JAVA_OPTS = "-Xms512m -Xmx1024m -XX:PermSize=128m"


class VagrantLxcBoot:

    def __init__(self, args):
        self.working_dir = args.working_dir
        self.cosmo_version = args.cosmo_version
        self.jar_name = "orchestrator-" + self.cosmo_version + "-all"

    @retry(stop='stop_after_attempt', stop_max_attempt_number=3, wait_fixed=3000)
    def install_fabric(self):
        return_code = subprocess.call(["sudo", "pip", "install", "fabric"])
        if return_code != 0:
            raise CalledProcessError(cmd="pip install fabric", returncode=1, output=sys.stderr)

    def run_fabric(self, command):
        from fabric.api import local as lrun
        lrun(command)

    @retry(stop='stop_after_attempt', stop_max_attempt_number=3, wait_fixed=3000)
    def run_with_retry_and_timeout(self, command):
        try:
            print command
            self.run_with_timeout(command)
        except SystemExit:  # lrun does not throw exception, but just exists the process
            raise CalledProcessError(cmd=command, returncode=1, output=sys.stderr)

    """
    Runs the command with a timeout of 10 minutes.
    Since most command are downloads, we assume that if 10 minutes are not enough
    then something is wrong. so we kill the process and let the retry decorator execute it again.
    """
    @timeout_decorator.timeout(60 * 10)
    def run_with_timeout(self, command):
        self.run_fabric(command)

    def pip(self, package):
        self.run_with_retry_and_timeout(self.sudo("pip install --timeout=120 {0}".format(package)))

    def sudo(self, command):
        return "sudo {0}".format(command)

    def apt_get(self, command):
        self.run_with_retry_and_timeout(self.sudo("apt-get {0}".format(command)))

    def add_apt(self, command):
        self.run_with_retry_and_timeout(self.sudo("add-apt-repository {0}".format(command)))

    def apt_key(self, command):
        self.run_with_retry_and_timeout(self.sudo("apt-key add {0}".format(command)))

    def wget(self, url):
        self.run_with_retry_and_timeout("wget {0} -P {1}/".format(url, self.working_dir))

    def install_rabbitmq(self):
        self.run_fabric(self.sudo("sed -i '2i deb http://www.rabbitmq.com/debian/ testing main' /etc/apt/sources.list"))

        self.wget("http://www.rabbitmq.com/rabbitmq-signing-key-public.asc")
        self.apt_key("rabbitmq-signing-key-public.asc")
        self.apt_get("update")
        self.apt_get("install -q -y erlang-nox")
        self.apt_get("install -y -f ")
        self.apt_get("install -q -y rabbitmq-server")
        self.run_fabric(self.sudo("rabbitmq-plugins enable rabbitmq_management"))
        self.run_fabric(self.sudo("rabbitmq-plugins enable rabbitmq_tracing"))
        self.run_fabric(self.sudo("service rabbitmq-server restart"))
        self.run_fabric(self.sudo("rabbitmqctl trace_on"))

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
        self.run_fabric(self.sudo("dpkg -i riemann_0.2.2_all.deb"))

    def install_java(self):
        self.apt_get("install -y openjdk-7-jdk")

    def install_celery(self):
        self.pip("billiard==2.7.3.28")
        self.pip("celery==3.0.19")
        self.pip("python-vagrant")
        self.pip("bernhard")

    def install_vagrant(self):
        self.wget(
            "http://files.vagrantup.com/packages/22b76517d6ccd4ef232a4b4ecbaa276aff8037b8/vagrant_1.2.6_x86_64.deb"
        )
        self.run_fabric(self.sudo("dpkg -i vagrant_1.2.6_x86_64.deb"))
        self.install_vagrant_lxc()
        self.add_lxc_box("precise64", "http://dl.dropbox.com/u/13510779/lxc-precise-amd64-2013-07-12.box")

    def install_vagrant_lxc(self):
        self.run_fabric("vagrant plugin install vagrant-lxc")

    """
    Currently not used. provides some more functionallity between the actual host and the virtual box vagrant guest.
    See http://www.virtualbox.org/manual/ch04.html
    """
    def install_guest_additions(self):
        self.apt_get("install -q -y linux-headers-3.8.0-19-generic dkms")
        self.run_fabric("echo 'Downloading VBox Guest Additions...'")
        self.wget("-q http://dlc.sun.com.edgesuite.net/virtualbox/4.2.12/VBoxGuestAdditions_4.2.12.iso")

        guest_additions_script = """mount -o loop,ro /home/vagrant/VBoxGuestAdditions_4.2.12.iso /mnt
echo yes | /mnt/VBoxLinuxAdditions.run
umount /mnt
rm /root/guest_additions.sh
"""

        self.run_fabric("echo -e '" + guest_additions_script + "' > /root/guest_additions.sh")
        self.run_fabric("chmod 700 /root/guest_additions.sh")
        self.run_fabric(
            "sed -i -E 's#^exit 0#[ -x /root/guest_additions.sh ] \\&\\& /root/guest_additions.sh#' /etc/rc.local"
        )
        self.run_fabric("echo 'Installation of VBox Guest Additions is proceeding in the background.'")
        self.run_fabric("echo '\"vagrant reload\" can be used in about 2 minutes to activate the new guest additions.'")

    def install_cosmo(self):

        run_script = """#!/bin/sh
ARGS=\"$@\"
export VAGRANT_DEFAULT_PROVIDER=lxc
java {0} -jar {1}/cosmo.jar $ARGS
""".format(JAVA_OPTS, self.working_dir)

        get_cosmo = "https://s3.amazonaws.com/cosmo-snapshot-maven-repository/travisci/home/travis/" \
                    ".m2/repository/org/cloudifysource/cosmo/orchestrator/" + self.cosmo_version + "/" + self\
            .jar_name + ".jar"

        self.wget(get_cosmo)

        self.run_fabric("mv {0}/{1}.jar cosmo.jar".format(self.working_dir, self.jar_name))

        script_path = self.working_dir + "/cosmo.sh"
        cosmo_exec = open(script_path, "w")
        cosmo_exec.write(run_script)

        self.run_fabric("chmod +x " + script_path)

        self.run_fabric("echo \"alias cosmo='{0}/cosmo.sh'\" > {1}/.bash_aliases".format(self.working_dir, USER_HOME))

    def add_lxc_box(self, name, url):
        self.run_with_retry_and_timeout(
            "vagrant box add {0} {1}".format(name, url)
        )

    def reboot(self):
        self.run_fabric("shutdown -r +1")

    def bootstrap(self):
        self.install_fabric()
        self.install_lxc_docker()
        self.install_kernel()
        self.install_rabbitmq()
        self.install_riemann()
        self.install_celery()
        self.install_vagrant()
        self.install_java()
        self.install_cosmo()
        print "Manager boot completed"

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

    vagrant_boot = VagrantLxcBoot(parser.parse_args())
    vagrant_boot.bootstrap()